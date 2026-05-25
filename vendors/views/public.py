from decimal import Decimal

from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.actions.admin_actions import CheckUserAvailabilityAction
from accounts.models import Address
from helpers.cache_helpers import cached_api_response
from accounts.serializers import UserProfileSerializer
from helpers.delivery_quotes import quote_vendor_delivery
from helpers.vendor_hours import is_vendor_open_now
from orders.models import OrderItem
from products.models import Product
from products.serializers import CategorySerializer, ProductSerializer
from vendors.data import VendorProductRepository, VendorRepository
from vendors.models import Vendor
from vendors.serializers.public import VendorListSerializer, VendorRegistrationSerializer, VendorSerializer


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _build_request_address(request) -> Address | None:
    lat = request.query_params.get("lat")
    lng = request.query_params.get("lng")
    if lat is None or lng is None:
        return None

    try:
        return Address(
            user=request.user if getattr(request.user, "is_authenticated", False) else None,
            full_name="Customer",
            phone="",
            address_line1="Selected location",
            city=request.query_params.get("city", ""),
            state=request.query_params.get("state", ""),
            postal_code=request.query_params.get("postal_code", ""),
            latitude=Decimal(str(lat)),
            longitude=Decimal(str(lng)),
        )
    except Exception:
        return None


def _get_matching_product_names(vendor, product_query: str) -> list[str]:
    if not product_query:
        return []
    search_q = Q()
    for term in [part.strip() for part in product_query.split(",") if part.strip()]:
        search_q |= (
            Q(name__icontains=term)
            | Q(search_keywords__icontains=term)
            | Q(description__icontains=term)
            | Q(brand__icontains=term)
            | Q(category__name__icontains=term)
        )
    if not search_q:
        return []
    products = Product.objects.filter(
        vendor=vendor,
        approval_status=Product.APPROVAL_STATUS_APPROVED,
        status="active",
        is_available=True,
        stock__gt=0,
        category__is_active=True,
        category__show_in_customer_ui=True,
    ).filter(search_q)
    return list(products.values_list("name", flat=True).distinct()[:3])


def _serialize_vendor_cards(request, vendors, address: Address | None, product_query: str = "") -> list[dict]:
    cards = []

    for vendor in vendors:
        payload = VendorListSerializer(vendor, context={"request": request}).data
        payload["matched_products_preview"] = _get_matching_product_names(vendor, product_query)

        if address:
            quote = quote_vendor_delivery(vendor, address)
            payload.update(quote.as_dict())
        else:
            payload.setdefault("distance_km", None)
            payload.setdefault("estimated_delivery_minutes", None)
            payload.setdefault("estimated_delivery_label", "")
            payload.setdefault("far_order_eta_label", "")
            payload.setdefault("vehicle_type", "")
            payload.setdefault("vehicle_reason", "")
            payload.setdefault("is_far_delivery", False)
            payload.setdefault("requires_far_delivery_confirmation", False)
            payload.setdefault("within_instant_radius", False)
            payload.setdefault("same_state", False)
            payload.setdefault("is_serviceable", True)
            payload.setdefault("serviceability_error", "")
            payload.setdefault("max_supported_distance_km", 0)
            payload.setdefault("instant_radius_km", 0)

        payload["has_previously_ordered"] = bool(getattr(vendor, "has_previously_ordered", False))
        cards.append(payload)

    cards.sort(
        key=lambda item: (
            0 if item.get("has_previously_ordered") else 1,
            item.get("distance_km") if item.get("distance_km") is not None else 999999,
            item.get("store_name", "").lower(),
        )
    )
    return cards


def _sort_vendor_cards(cards: list[dict], sort_key: str) -> list[dict]:
    if sort_key == "rating":
        return sorted(
            cards,
            key=lambda item: (
                -float(item.get("average_rating") or 0),
                item.get("distance_km") if item.get("distance_km") is not None else 999999,
                item.get("store_name", "").lower(),
            ),
        )
    if sort_key == "distance":
        return sorted(
            cards,
            key=lambda item: (
                item.get("distance_km") if item.get("distance_km") is not None else 999999,
                item.get("store_name", "").lower(),
            ),
        )
    if sort_key == "min_order_asc":
        return sorted(
            cards,
            key=lambda item: (
                float(item.get("min_order_amount") or 0),
                item.get("distance_km") if item.get("distance_km") is not None else 999999,
                item.get("store_name", "").lower(),
            ),
        )
    return sorted(
        cards,
        key=lambda item: (
            0 if item.get("has_previously_ordered") else 1,
            item.get("distance_km") if item.get("distance_km") is not None else 999999,
            item.get("store_name", "").lower(),
        ),
    )


class VendorRegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VendorRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendor = serializer.save()
        refresh = RefreshToken.for_user(vendor.user)
        return Response(
            {
                "user": UserProfileSerializer(vendor.user).data,
                "vendor": VendorSerializer(vendor).data,
                "vendor_status": vendor.status,
                "tokens": {"refresh": str(refresh), "access": str(refresh.access_token)},
            },
            status=status.HTTP_201_CREATED,
        )


class VendorIdentityAvailabilityView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            result = CheckUserAvailabilityAction().execute(
                field=request.data.get("field", ""),
                value=request.data.get("value", ""),
            )
            return Response(result)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class VendorListView(APIView):
    permission_classes = [AllowAny]
    pagination_class = StandardPagination

    def get(self, request):
        return cached_api_response(
            request,
            'vendors:list',
            60,
            lambda: self._get_uncached(request),
            include_user=True,
        )

    def _get_uncached(self, request):
        repo = VendorRepository()
        address = _build_request_address(request)
        search = request.query_params.get("search", "").strip()
        search_mode = request.query_params.get("search_mode", "browse").strip() or "browse"
        category = request.query_params.get("category")
        max_price = request.query_params.get("maxPrice") or request.query_params.get("max_price")
        min_rating = request.query_params.get("minRating") or request.query_params.get("min_rating")
        offers = request.query_params.get("offersOnly") or request.query_params.get("offers")
        state = request.query_params.get("state")
        city = request.query_params.get("city")
        sort_key = request.query_params.get("sort", "relevance").strip() or "relevance"
        area = request.query_params.get("area", "").strip()
        group_by_area = request.query_params.get("group_by_area", "").lower() == "true"
        include_far_same_state = request.query_params.get("include_far_same_state", "").lower() == "true"
        product_query = request.query_params.get("product_query", "").strip()

        if search_mode == "global_item":
            query = product_query or search
            if not query:
                return Response([])
            vendors = (
                repo.get_vendors_selling_product_query(query, state=state)
                | repo.get_approved_vendors_in_state(state=state, search=query, category=category)
            )
        elif search_mode == "manual_far" or include_far_same_state:
            if not state:
                return Response([])
            vendors = repo.get_approved_vendors_in_state(state=state, search=search, category=category)
        else:
            try:
                max_price_value = Decimal(str(max_price)) if max_price else None
            except Exception:
                max_price_value = None
            try:
                min_rating_value = Decimal(str(min_rating)) if min_rating else None
            except Exception:
                min_rating_value = None
            vendors = repo.get_approved_vendors(
                search=search,
                category=category,
                max_price=max_price_value,
                min_rating=min_rating_value,
                offers=offers,
            )

        if city:
            vendors = vendors.filter(city__iexact=city)

        if getattr(request.user, "is_authenticated", False):
            vendors = repo.annotate_previous_order_flag(vendors, request.user)
        vendors = repo.with_available_products(vendors)

        cards = _serialize_vendor_cards(request, list(vendors.distinct()), address, product_query=product_query or search)
        cards = [card for card in cards if card.get("is_serviceable", True)]
        cards = _sort_vendor_cards(cards, sort_key)
        grouped_cards = {
            "nearby": [card for card in cards if card.get("within_instant_radius")],
            "extended": [card for card in cards if card.get("within_instant_radius") is False],
        }

        if area == "nearby" or (not area and search_mode == "nearby" and address):
            cards = [card for card in cards if card.get("within_instant_radius")]
        elif area == "extended":
            cards = [card for card in cards if card.get("within_instant_radius") is False]
        elif search_mode == "global_item":
            cards = [card for card in cards if card.get("matched_products_preview")]

        summary = {
            "total": len(cards),
            "nearby": len(grouped_cards["nearby"]),
            "extended": len(grouped_cards["extended"]),
        }
        cities = repo.get_delivery_cities(state=state, category=category)

        if group_by_area:
            return Response({
                "count": len(cards),
                "results": cards,
                "groups": grouped_cards,
                "summary": summary,
                "cities": cities,
            })

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(cards, request)
        if page is not None:
            response = paginator.get_paginated_response(page)
            response.data["summary"] = summary
            response.data["cities"] = cities
            return response
        return Response(cards)


class VendorDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = VendorSerializer

    def get_queryset(self):
        return VendorRepository().filter(status="approved")

    def retrieve(self, request, *args, **kwargs):
        return cached_api_response(
            request,
            f'vendors:detail:{kwargs.get("pk")}',
            90,
            lambda: self._retrieve_uncached(request, *args, **kwargs),
            include_user=False,
        )

    def _retrieve_uncached(self, request, *args, **kwargs):
        vendor = self.get_object()
        vendor_data = VendorSerializer(vendor, context={"request": request}).data
        product_search = request.query_params.get("product_search") or request.query_params.get("q")
        category = request.query_params.get("product_category") or request.query_params.get("category")
        min_rating = request.query_params.get("min_rating")
        min_price = request.query_params.get("min_price")
        max_price = request.query_params.get("max_price")
        try:
            min_rating_value = Decimal(str(min_rating)) if min_rating else None
        except Exception:
            min_rating_value = None
        try:
            min_price_value = Decimal(str(min_price)) if min_price else None
        except Exception:
            min_price_value = None
        try:
            max_price_value = Decimal(str(max_price)) if max_price else None
        except Exception:
            max_price_value = None
        available_products = VendorProductRepository().get_customer_visible_for_vendor(
            vendor=vendor,
            search=(product_search or "").strip(),
            category=(category or "").strip(),
            min_rating=min_rating_value,
            min_price=min_price_value,
            max_price=max_price_value,
            availability=request.query_params.get("availability") or request.query_params.get("in_stock"),
            offers=request.query_params.get("offers"),
            product_type=request.query_params.get("product_type"),
            sort=request.query_params.get("product_sort") or request.query_params.get("sort"),
        )
        category_products = VendorProductRepository().get_customer_visible_for_vendor(vendor=vendor)
        available_categories = []
        seen_category_ids = set()
        for product in category_products:
            category = product.category
            if not category or category.id in seen_category_ids:
                continue
            seen_category_ids.add(category.id)
            available_categories.append(category)

        vendor_data["products"] = ProductSerializer(
            available_products,
            many=True,
            context={"request": request},
        ).data
        vendor_data["available_categories"] = CategorySerializer(
            available_categories,
            many=True,
            context={"request": request},
        ).data

        address = _build_request_address(request)
        if address:
            quote = quote_vendor_delivery(vendor, address)
            vendor_data.update(quote.as_dict())
        return Response(vendor_data)


class NearbyVendorsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return cached_api_response(
            request,
            'vendors:nearby',
            60,
            lambda: self._get_uncached(request),
            include_user=True,
        )

    def _get_uncached(self, request):
        address = _build_request_address(request)
        if not address:
            return Response({"error": "lat and lng reqd."}, status=status.HTTP_400_BAD_REQUEST)

        category = request.query_params.get("category")
        repo = VendorRepository()
        vendors = repo.get_approved_vendors(category=category)
        if getattr(request.user, "is_authenticated", False):
            vendors = repo.annotate_previous_order_flag(vendors, request.user)

        cards = _serialize_vendor_cards(request, list(vendors.distinct()), address)
        cards = [card for card in cards if card.get("within_instant_radius")]
        return Response(cards)


class VendorRecommendationsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        return cached_api_response(
            request,
            f'vendors:recommendations:{pk}',
            90,
            lambda: self._get_uncached(request, pk),
            include_user=True,
        )

    def _get_uncached(self, request, pk):
        try:
            vendor = Vendor.objects.get(pk=pk, status="approved")
        except Vendor.DoesNotExist:
            return Response({"error": "Store not found."}, status=status.HTTP_404_NOT_FOUND)

        base_qs = Product.objects.filter(
            vendor=vendor,
            approval_status=Product.APPROVAL_STATUS_APPROVED,
            status="active",
            is_available=True,
            stock__gt=0,
            category__is_active=True,
            category__show_in_customer_ui=True,
        ).select_related("category")
        previous_ids = set()
        if getattr(request.user, "is_authenticated", False):
            previous_ids = set(
                OrderItem.objects.filter(
                    order__customer=request.user,
                    order__vendor=vendor,
                    product__isnull=False,
                ).values_list("product_id", flat=True)
            )
        previous = list(base_qs.filter(id__in=previous_ids).order_by("-total_orders", "-average_rating")[:8])
        featured = list(base_qs.filter(is_featured=True).exclude(id__in=[p.id for p in previous]).order_by("-average_rating", "-total_orders")[:8])
        popular = list(base_qs.exclude(id__in=[p.id for p in previous + featured]).order_by("-total_orders", "-average_rating")[:12])
        selected = (previous + featured + popular)[:16]

        results = []
        hour = timezone.localtime(timezone.now()).hour
        time_reason = "morning_pick" if 5 <= hour < 12 else "evening_pick" if 17 <= hour < 22 else "popular_now"
        for product in selected:
            if product.id in previous_ids:
                reason = "previously_bought"
            elif product.is_featured:
                reason = "vendor_promoted"
            elif product.total_orders > 0:
                reason = "popular_in_store"
            else:
                reason = time_reason
            results.append({
                "product": ProductSerializer(product, context={"request": request}).data,
                "reason": reason,
                "store_id": str(vendor.id),
                "store_name": vendor.store_name,
            })

        categories = list(
            base_qs.exclude(category__isnull=True)
            .values("category_id", "category__name")
            .distinct()[:8]
        )
        return Response({
            "store_id": str(vendor.id),
            "store_name": vendor.store_name,
            "results": results,
            "recommended_categories": [
                {"id": str(item["category_id"]), "name": item["category__name"]}
                for item in categories
            ],
        })
