from django.db import transaction
from django.utils import timezone

from backend.events import order_cancelled
from orders.actions.base import BaseAction
from orders.actions import OrderCancellationEffectsAction
from orders.data.order_repo import OrderRepository
from orders.models import Order
from orders.models.setting import PlatformSetting


class CancelOrderAction(BaseAction):
    @transaction.atomic
    def execute(self, order_id, user) -> Order:
        try:
            order = OrderRepository.get_locked(order_id, customer=user)
        except Order.DoesNotExist:
            raise ValueError('Order not found.')

        customer_allowed = ['placed', 'confirmed', 'preparing', 'ready']
        if order.status not in customer_allowed:
            if order.status == 'delivered':
                raise ValueError('Delivered orders cannot be cancelled.')
            raise ValueError(
                'Orders that are already dispatched or delivered cannot be cancelled. '
                'Please contact support.'
            )

        setting = PlatformSetting.get_setting()
        if setting.cancellation_window_minutes > 0:
            elapsed_minutes = (timezone.now() - order.placed_at).total_seconds() / 60
            if elapsed_minutes > setting.cancellation_window_minutes:
                raise ValueError(
                    f'Orders can only be cancelled within {setting.cancellation_window_minutes} '
                    f'minutes of placement. This order was placed {int(elapsed_minutes)} minutes ago.'
                )

        order.status = 'cancelled'
        order.save(update_fields=['status', 'updated_at'])
        OrderRepository.add_tracking(order=order, status='cancelled', description='Order cancelled by customer.')
        OrderCancellationEffectsAction().execute(order)
        order_cancelled.send(sender=Order, order=order)
        return order
