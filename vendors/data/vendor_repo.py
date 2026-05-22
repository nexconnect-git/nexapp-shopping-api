from django.db.models import BooleanField, Count, DecimalField, Exists, F, OuterRef, Prefetch, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from products.models import Product
from orders.models import Order
from vendors.data.base import BaseRepository
from vendors.models import Vendor


def _split_search_terms(query):
    seen = set()
    terms = []
    for part in str(query or "").split(","):
        value = " ".join(part.strip().split())
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            terms.append(value)
    return terms


def _product_query_for_terms(terms):
    search_q = Q()
    for term in terms:
        search_q |= (
            Q(name__icontains=term)
            | Q(search_keywords__icontains=term)
            | Q(description__icontains=term)
            | Q(brand__icontains=term)
            | Q(category__name__icontains=term)
        )
    return search_q


class VendorRepository(BaseRepository):
    def __init__(self):
        super().__init__(model=Vendor)

    def get_approved_vendors(self, search=None, city=None, is_open=None, is_featured=None, category=None, max_price=None, min_rating=None, offers=None):
        qs = self.model.objects.filter(status="approved")
        if search:
            qs = qs.filter(
                Q(store_name__icontains=search)
                | Q(description__icontains=search)
                | Q(city__icontains=search)
            )
        if city:
            qs = qs.filter(city__iexact=city)
        if is_open is not None:
            qs = qs.filter(is_open=is_open.lower() == "true")
        if is_featured is not None:
            qs = qs.filter(is_featured=is_featured.lower() == "true")
        if category:
            qs = qs.filter(
                Q(products__category__slug=category) |
                Q(products__category__name__iexact=category) |
                Q(products__category__parent__slug=category) |
                Q(products__category__parent__name__iexact=category),
                products__status="active",
                products__is_available=True,
                products__stock__gt=0,
                products__category__is_active=True,
                products__category__show_in_customer_ui=True,
            ).distinct()
        if max_price is not None:
            qs = qs.filter(products__price__lte=max_price).distinct()
        if min_rating is not None:
            qs = qs.filter(products__average_rating__gte=min_rating).distinct()
        if str(offers or "").lower() in {"true", "1", "yes"}:
            qs = qs.filter(products__compare_price__gt=F("products__price")).distinct()
        return qs

    def get_approved_vendors_in_state(self, state, search=None, category=None):
        qs = self.get_approved_vendors(search=search, category=category)
        if state:
            qs = qs.filter(state__iexact=state)
        return qs

    def get_delivery_cities(self, state=None, category=None):
        qs = self.get_approved_vendors(category=category)
        if state:
            qs = qs.filter(state__iexact=state)
        return list(
            qs.exclude(city__isnull=True)
            .exclude(city="")
            .order_by("city")
            .values_list("city", flat=True)
            .distinct()
        )

    def get_vendors_selling_product_query(self, query, state=None):
        terms = _split_search_terms(query)
        if not terms:
            return self.model.objects.none()
        product_vendor_ids = Product.objects.filter(
            approval_status=Product.APPROVAL_STATUS_APPROVED,
            status="active",
            is_available=True,
            stock__gt=0,
            category__is_active=True,
            category__show_in_customer_ui=True,
        ).filter(_product_query_for_terms(terms)).values("vendor_id").distinct()
        qs = self.model.objects.filter(status="approved", id__in=Subquery(product_vendor_ids))
        if state:
            qs = qs.filter(state__iexact=state)
        return qs

    def with_available_products(self, queryset):
        products = (
            Product.objects.filter(
                approval_status=Product.APPROVAL_STATUS_APPROVED,
                status="active",
                is_available=True,
                stock__gt=0,
                category__is_active=True,
                category__show_in_customer_ui=True,
            )
            .select_related("category", "catalog_product")
            .prefetch_related("images", "catalog_product__images")
            .order_by("category__display_order", "category__name", "name")
        )
        return queryset.prefetch_related(Prefetch("products", queryset=products, to_attr="available_products"))

    def annotate_previous_order_flag(self, queryset, customer):
        if not customer or not getattr(customer, "is_authenticated", False):
            return queryset.annotate(has_previously_ordered=Value(False, output_field=BooleanField()))

        previous_orders = Order.objects.filter(
            customer=customer,
            vendor_id=OuterRef("pk"),
        )
        return queryset.annotate(has_previously_ordered=Exists(previous_orders))

    def get_all_with_users(self, search=None, status=None):
        qs = self.model.objects.select_related("user").order_by("-created_at")
        if search:
            qs = (qs.filter(store_name__icontains=search) | self.model.objects.filter(city__icontains=search)).distinct()
        if status:
            qs = qs.filter(status=status)
        return qs

class VendorProductRepository(BaseRepository):
    def __init__(self):
        super().__init__(model=Product)

    def get_low_stock_for_vendor(self, vendor):
        return self.filter(
            vendor=vendor,
            stock__lte=F("low_stock_threshold"),
            low_stock_threshold__gt=0
        )

    def get_customer_visible_for_vendor(
        self,
        vendor,
        search=None,
        category=None,
        min_rating=None,
        min_price=None,
        max_price=None,
        availability=None,
        offers=None,
        product_type=None,
        sort=None,
    ):
        qs = self.filter(
            vendor=vendor,
            approval_status=Product.APPROVAL_STATUS_APPROVED,
            status="active",
            is_available=True,
            stock__gt=0,
            category__is_active=True,
            category__show_in_customer_ui=True,
        ).select_related("category", "catalog_product").prefetch_related("images", "catalog_product__images")

        if search:
            qs = qs.filter(_product_query_for_terms(_split_search_terms(search)))
        if category and str(category).lower() != "all":
            qs = qs.filter(
                Q(category__slug=category)
                | Q(category__name__iexact=category)
                | Q(category__parent__slug=category)
                | Q(category__parent__name__iexact=category)
            )
        if min_rating is not None:
            qs = qs.filter(average_rating__gte=min_rating)
        if min_price is not None:
            qs = qs.filter(price__gte=min_price)
        if max_price is not None:
            qs = qs.filter(price__lte=max_price)
        if str(availability or "").lower() in {"true", "1", "available", "in_stock"}:
            qs = qs.filter(is_available=True, stock__gt=0)
        if str(offers or "").lower() in {"true", "1", "yes"}:
            qs = qs.filter(compare_price__gt=F("price"))
        if str(product_type or "").lower() == "veg":
            qs = qs.filter(
                Q(search_keywords__icontains="veg")
                | Q(name__icontains="veg")
                | Q(description__icontains="vegetarian")
                | Q(category__name__icontains="veg")
            )

        sort_key = str(sort or "relevance").lower()
        if sort_key in {"price", "price_asc", "price_low_to_high"}:
            return qs.order_by("price", "category__display_order", "name")
        if sort_key in {"rating", "top_rated"}:
            return qs.order_by("-average_rating", "-total_orders", "category__display_order", "name")
        if sort_key in {"popular", "popularity"}:
            return qs.order_by("-total_orders", "-average_rating", "category__display_order", "name")
        return qs.order_by("category__display_order", "category__name", "name")

    def get_products_for_vendor_with_growth(self, vendor):
        return self.filter(vendor=vendor).annotate(
            image_count=Count("images", distinct=True),
            revenue=Coalesce(
                Sum("orderitem__subtotal"),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            sales_count=Coalesce(Sum("orderitem__quantity"), Value(0)),
        )
