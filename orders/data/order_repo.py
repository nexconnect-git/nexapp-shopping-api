from django.db.models import Q
from orders.models import Order, OrderTracking, OrderRating


class OrderRepository:

    @staticmethod
    def get_customer_orders(user, status_filter=None):
        qs = Order.objects.filter(customer=user)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    @staticmethod
    def get_customer_order_detail(user, pk):
        return Order.objects.filter(
            customer=user
        ).prefetch_related("items", "tracking").get(pk=pk)

    @staticmethod
    def get_by_id(pk, prefetch=None):
        qs = Order.objects.all()
        if prefetch:
            qs = qs.prefetch_related(*prefetch)
        return qs.get(pk=pk)

    @staticmethod
    def get_tracking(order_id, user):
        return OrderTracking.objects.filter(
            order_id=order_id, order__customer=user
        )

    @staticmethod
    def get_all_admin(status_filter=None, search=None, vendor=None, customer=None, partner=None):
        qs = Order.objects.select_related("customer", "vendor").order_by("-placed_at")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if search:
            qs = qs.filter(order_number__icontains=search)
        if vendor:
            qs = qs.filter(vendor_id=vendor)
        if customer:
            qs = qs.filter(customer_id=customer)
        if partner:
            # Map DeliveryPartner UUID to underlying User UUID
            from delivery.models import DeliveryPartner
            try:
                dp = DeliveryPartner.objects.get(id=partner)
                qs = qs.filter(delivery_partner_id=dp.user_id)
            except (DeliveryPartner.DoesNotExist, ValueError):
                # Fallback in case it's actually a user UUID
                qs = qs.filter(delivery_partner_id=partner)
        return qs

    @staticmethod
    def get_base_queryset():
        """Return the base Order queryset for arbitrary filtering."""
        return Order.objects.all()
