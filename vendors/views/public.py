from decimal import Decimal

from django.db.models import Q
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Address
from accounts.serializers import UserProfileSerializer
from helpers.delivery_quotes import CUSTOMER_DISCOVERY_RADIUS_KM, quote_vendor_delivery
from helpers.vendor_hours import is_vendor_open_now
from products.models import Product
from products.serializers import ProductSerializer
from vendors.data import VendorProductRepository, VendorRepository
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
    products = Product.objects.filter(
        vendor=vendor,
        approval_status=Product.APPROVAL_STATUS_APPROVED,
        status="active",
        is_available=True,
        stock__gt=0,
    ).filter(
        Q(name__icontains=product_query)
        | Q(search_keywords__icontains=product_query)
        | Q(description__icontains=product_query)
        | Q(brand__icontains=product_query)
    )
    return list(products.values_list("name", flat=True).distinct()[:3])


def _serialize_vendor_cards(request, vendors, address: Address | None, product_query: str = "") -> list[dict]:
    cards = []

    for vendor in vendors:
        if not is_vendor_open_now(vendor):
            continue

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


class VendorListView(APIView):
    permission_classes = [AllowAny]
    pagination_class = StandardPagination

    def get(self, request):
        repo = VendorRepository()
        address = _build_request_address(request)
        search = request.query_params.get("search", "").strip()
        search_mode = request.query_params.get("search_mode", "browse").strip() or "browse"
        category = request.query_params.get("category")
        state = request.query_params.get("state")
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
            vendors = repo.get_approved_vendors(search=search, category=category)

        if getattr(request.user, "is_authenticated", False):
            vendors = repo.annotate_previous_order_flag(vendors, request.user)

        cards = _serialize_vendor_cards(request, list(vendors.distinct()), address, product_query=product_query or search)
        cards = [card for card in cards if card.get("is_serviceable", True)]

        if search_mode == "nearby" and address:
            cards = [card for card in cards if card.get("within_instant_radius")]
        elif search_mode == "global_item":
            cards = [card for card in cards if card.get("matched_products_preview")]

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(cards, request)
        if page is not None:
            return paginator.get_paginated_response(page)
        return Response(cards)


class VendorDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = VendorSerializer

    def get_queryset(self):
        return VendorRepository().filter(status="approved")

    def retrieve(self, request, *args, **kwargs):
        vendor = self.get_object()
        vendor_data = VendorSerializer(vendor, context={"request": request}).data
        available_products = VendorProductRepository().filter(vendor=vendor, is_available=True)
        vendor_data["products"] = ProductSerializer(
            available_products,
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
