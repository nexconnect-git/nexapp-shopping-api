import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from accounts.actions.wallet_actions import CreditWalletAction
from backend.events import order_cancelled
from orders.actions.base import BaseAction
from orders.actions.refund_actions import IssueRazorpayRefundAction
from orders.models import InventoryReservation, Order, OrderTracking
from orders.models.setting import PlatformSetting
from products.models import Product


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
        self._restore_inventory(order)
        self._release_reservations(order)
        self._refund_wallet(order)
        self._refund_razorpay(order)
        order_cancelled.send(sender=Order, order=order)
        return order

    def _restore_inventory(self, order):
        for item in order.items.select_related('product').all():
            if item.product:
                Product.objects.filter(pk=item.product.pk).update(stock=F('stock') + item.quantity)
                if item.product.status == 'sold_out':
                    Product.objects.filter(pk=item.product.pk).update(status='active')

    def _release_reservations(self, order):
        InventoryReservation.objects.filter(
            order=order,
            status=InventoryReservation.STATUS_COMMITTED,
        ).update(
            status=InventoryReservation.STATUS_RELEASED,
            released_at=timezone.now(),
            updated_at=timezone.now(),
        )

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
