from django.db import transaction

from orders.actions import OrderCancellationEffectsAction, SettleDeliveredOrderAction
from orders.data.order_repo import OrderRepository
from backend.events import order_status_updated
from orders.actions.base import BaseAction
from orders.models import Order


class AdminUpdateOrderStatusAction(BaseAction):
    valid_statuses = ['placed', 'confirmed', 'preparing', 'ready', 'picked_up', 'on_the_way', 'delivered', 'cancelled']

    @transaction.atomic
    def execute(self, order_id, new_status, admin_user) -> Order:
        try:
            order = OrderRepository.get_locked(order_id)
        except Order.DoesNotExist:
            raise ValueError('Order not found.')

        if new_status not in self.valid_statuses:
            raise ValueError('Invalid status.')
        if new_status == order.status:
            return order
        if order.status in ('delivered', 'cancelled'):
            raise ValueError('Completed or cancelled orders cannot change status.')
        if new_status != 'cancelled' and self.valid_statuses.index(new_status) < self.valid_statuses.index(order.status):
            raise ValueError('Orders cannot move backwards through delivery statuses.')

        old_status = order.status
        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])

        if new_status == 'cancelled' and old_status != 'cancelled':
            OrderCancellationEffectsAction().execute(order)

        OrderRepository.add_tracking(
            order=order,
            status=new_status,
            description=f'Status updated by admin to {new_status}.',
        )
        order_status_updated.send(sender=Order, order=order, new_status=new_status, old_status=old_status)

        if new_status == 'delivered' and old_status != 'delivered':
            SettleDeliveredOrderAction().execute(order)

        return order
