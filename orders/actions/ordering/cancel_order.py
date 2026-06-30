import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from accounts.actions.wallet_actions import CreditWalletAction
from backend.events import order_cancelled
from orders.actions.base import BaseAction
from orders.actions.inventory_reservations import ReservationInventoryAction
from orders.actions.refund_actions import IssueRazorpayRefundAction
from orders.models import Order, OrderTracking
from orders.models.setting import PlatformSetting


logger = logging.getLogger(__name__)


class CancelOrderAction(BaseAction):
    @transaction.atomic
    def execute(self, order_id, user) -> Order:
        try:
            order = Order.objects.get(pk=order_id, customer=user)
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
        OrderTracking.objects.create(order=order, status='cancelled', description='Order cancelled by customer.')
        ReservationInventoryAction().release_order(order, reason="cancelled")
        self._refund_wallet(order)
        self._refund_razorpay(order)
        order_cancelled.send(sender=Order, order=order)
        return order

    def _refund_wallet(self, order):
        if order.wallet_discount <= Decimal('0'):
            return
        try:
            CreditWalletAction.execute(
                user=order.customer,
                amount=order.wallet_discount,
                source='refund',
                reference_id=str(order.pk),
                description=f'Wallet refund for cancelled order {order.order_number}',
            )
        except Exception as exc:
            logger.warning('Wallet refund failed for order %s: %s', order.order_number, exc)

    def _refund_razorpay(self, order):
        if order.payment_method != 'razorpay' or not order.is_payment_verified or order.razorpay_refund_id:
            return
        try:
            IssueRazorpayRefundAction().execute(order)
        except Exception as exc:
            logger.warning('Refund failed for order %s: %s', order.order_number, exc)
