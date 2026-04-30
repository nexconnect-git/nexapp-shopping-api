from django.db.models import BooleanField, Count, DecimalField, Exists, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from products.models import Product
from orders.models import Order
from vendors.data.base import BaseRepository
from vendors.models import Vendor

class VendorRepository(BaseRepository):
    def __init__(self):
        super().__init__(model=Vendor)

    def get_approved_vendors(self, search=None, city=None, is_open=None, is_featured=None, category=None):
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
                Q(products__category__parent__slug=category)
            ).distinct()
        return qs

    def get_approved_vendors_in_state(self, state, search=None, category=None):
        qs = self.get_approved_vendors(search=search, category=category)
        if state:
            qs = qs.filter(state__iexact=state)
        return qs

    def get_vendors_selling_product_query(self, query, state=None):
        product_vendor_ids = Product.objects.filter(
            approval_status=Product.APPROVAL_STATUS_APPROVED,
            status="active",
            is_available=True,
            stock__gt=0,
        ).filter(
            Q(name__icontains=query)
            | Q(search_keywords__icontains=query)
            | Q(description__icontains=query)
            | Q(brand__icontains=query)
        ).values("vendor_id").distinct()
        qs = self.model.objects.filter(status="approved", id__in=Subquery(product_vendor_ids))
        if state:
            qs = qs.filter(state__iexact=state)
        return qs

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
