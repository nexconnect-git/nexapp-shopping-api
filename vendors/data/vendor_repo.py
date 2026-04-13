from .base import BaseRepository
from vendors.models import Vendor
from django.db.models import Q
from products.models import Product

class VendorRepository(BaseRepository):
    def __init__(self):
        super().__init__(model=Vendor)

    def get_approved_vendors(self, search=None, city=None, is_open=None, is_featured=None, category=None):
        qs = self.model.objects.filter(status="approved")
        if search:
            qs = qs.filter(store_name__icontains=search)
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
        from django.db.models import F
        return self.filter(
            vendor=vendor,
            stock__lte=F("low_stock_threshold"),
            low_stock_threshold__gt=0
        )
