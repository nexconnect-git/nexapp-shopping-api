from accounts.serializers import AddressSerializer
from backend.actions.customer_flow.constants import ACTIVE_ORDER_STATUSES
from backend.data import CustomerFlowRepository
from orders.actions.checkout import available_slots_for_cart
from orders.serializers import OrderSerializer
from vendors.serializers.public import VendorListSerializer


class GetCustomerOrderConfirmationAction:
    repository = CustomerFlowRepository

    def execute(self, request, pk) -> dict:
        order = self.repository.order_confirmation_order(request.user, pk)
        eta = order.estimated_delivery_time
        return {
            'id': str(order.id),
            'order_number': order.order_number,
            'status': order.status,
            'payment_status': OrderSerializer().get_payment_status(order),
            'payment_method': order.payment_method,
            'eta_label': f'{eta} min' if eta else '',
            'store': VendorListSerializer(order.vendor, context={'request': request}).data,
            'delivery_address': AddressSerializer(order.delivery_address).data if order.delivery_address else None,
            'total': str(order.total),
            'items_preview': [
                {
                    'id': str(item.id),
                    'name': item.product_name,
                    'quantity': item.quantity,
                    'subtotal': str(item.subtotal),
                }
                for item in order.items.all()[:4]
            ],
            'can_track': order.status in ACTIVE_ORDER_STATUSES,
            'can_cancel': order.status in ['placed', 'confirmed', 'preparing', 'ready'],
        }


class GetCustomerActiveOrderAction:
    repository = CustomerFlowRepository

    def execute(self, request) -> dict:
        if not getattr(request.user, 'is_authenticated', False):
            return {'active_order': None}
        order = self.repository.active_order(request.user, ACTIVE_ORDER_STATUSES)
        if not order:
            return {'active_order': None}
        return {'active_order': GetCustomerOrderConfirmationAction().execute(request, order.pk)}


class GetCustomerCheckoutSlotsAction:
    def execute(self, request) -> dict:
        slots = available_slots_for_cart(
            request.user,
            start_date=request.query_params.get('date'),
            days=min(int(request.query_params.get('days', 7)), 14),
        )
        return {'results': slots}
