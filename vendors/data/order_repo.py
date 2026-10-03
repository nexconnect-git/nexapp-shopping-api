from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from orders.models import Order
from vendors.data.base import BaseRepository

class VendorOrderRepository(BaseRepository):
    def __init__(self):
        super().__init__(model=Order)
        
    def get_vendor_orders(self, vendor, status_filter=None, params=None):
        qs = self.filter(vendor=vendor)
        if status_filter:
            qs = qs.filter(status=status_filter)
        qs = self._visible_to_vendor(qs, vendor)
        params = params or {}
        if params.get('search'):
            term = params['search']
            qs = qs.filter(Q(order_number__icontains=term) | Q(customer__first_name__icontains=term) | Q(customer__last_name__icontains=term) | Q(customer__username__icontains=term))
        for key, lookup in [('from', 'placed_at__date__gte'), ('to', 'placed_at__date__lte')]:
            date = parse_date(params.get(key, ''))
            if date:
                qs = qs.filter(**{lookup: date})
        return self.with_details(qs).order_by('-placed_at', 'id')

    def with_details(self, qs):
        return qs.select_related('customer', 'vendor', 'vendor__user', 'delivery_address', 'delivery_partner', 'delivery_partner__delivery_profile', 'assignment', 'rating', 'fulfillment_node').prefetch_related('items', 'tracking', 'invoices')

    def get_recent_orders(self, vendor, limit=10):
        qs = self._visible_to_vendor(self.filter(vendor=vendor), vendor)
        return self.with_details(qs).order_by("-placed_at")[:limit]

    def get_order_for_vendor(self, pk, vendor, status=None):
        qs = self.filter(pk=pk, vendor=vendor)
        if status:
            qs = qs.filter(status=status)
        try:
            return qs.get()
        except Order.DoesNotExist:
            return None

    def _visible_to_vendor(self, qs, vendor):
        release_at = timezone.now() + timedelta(
            minutes=int(getattr(vendor, "scheduled_buffer_min", 0) or 30)
        )
        return qs.filter(Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=release_at))
