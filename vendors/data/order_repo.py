from .base import BaseRepository
from orders.models import Order

class VendorOrderRepository(BaseRepository):
    def __init__(self):
        super().__init__(model=Order)
        
    def get_vendor_orders(self, vendor, status_filter=None):
        qs = self.filter(vendor=vendor)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.order_by("-placed_at")

    def get_recent_orders(self, vendor, limit=10):
        return self.filter(vendor=vendor).order_by("-placed_at")[:limit]

    def get_order_for_vendor(self, pk, vendor, status=None):
        qs = self.filter(pk=pk, vendor=vendor)
        if status:
            qs = qs.filter(status=status)
        try:
            return qs.get()
        except Order.DoesNotExist:
            return None
