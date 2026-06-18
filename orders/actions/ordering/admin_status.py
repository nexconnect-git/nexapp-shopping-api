import logging

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from accounts.actions.loyalty_actions import EarnLoyaltyPointsAction
from backend.events import order_status_updated
from orders.actions.base import BaseAction
from orders.actions.refund_actions import IssueRazorpayRefundAction
from orders.models import InventoryReservation, Order, OrderTracking
from products.models import Product


logger = logging.getLogger(__name__)


class AdminUpdateOrderStatusAction(BaseAction):
    valid_statuses = ['placed', 'confirmed', 'preparing', 'ready', 'picked_up', 'on_the_way', 'delivered', 'cancelled']

    @transaction.atomic
    def execute(self, order_id, new_status, admin_user) -> Order:
        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            raise ValueError('Order not found.')

        if new_status not in self.valid_statuses:
            raise ValueError('Invalid status.')
        if new_status == 'cancelled' and order.status == 'delivered':
            raise ValueError('Delivered orders cannot be cancelled.')

        old_status = order.status
        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])

        if new_status == 'cancelled' and old_status != 'cancelled':
            self._restore_inventory(order)
            self._release_reservations(order)
            self._refund_razorpay(order)

        OrderTracking.objects.create(
            order=order,
            status=new_status,
            description=f'Status updated by admin to {new_status}.',
        )
        order_status_updated.send(sender=Order, order=order, new_status=new_status, old_status=old_status)

        if new_status == 'delivered' and old_status != 'delivered':
            self._settle_delivered_order(order)

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

    def _refund_razorpay(self, order):
        if order.payment_method != 'razorpay' or not order.is_payment_verified or order.razorpay_refund_id:
            return
        try:
            IssueRazorpayRefundAction().execute(order)
        except Exception as exc:
            logger.warning('Admin cancel refund failed for order %s: %s', order.order_number, exc)

    def _settle_delivered_order(self, order):
        with transaction.atomic():
            self._credit_vendor(order)
            self._credit_delivery_partner(order)
            self._award_loyalty(order)

    def _credit_vendor(self, order):
        from vendors.actions.wallet_actions import VendorWalletAction

        vendor_earnings = order.subtotal - order.coupon_discount
        VendorWalletAction.credit_vendor(
            vendor_id=str(order.vendor.id),
            amount=vendor_earnings,
            source='order_earning',
            reference_id=str(order.id),
            description=f'Earnings from Order #{order.order_number}',
        )

    def _credit_delivery_partner(self, order):
        if not order.delivery_partner:
            return
        from delivery.models import DeliveryPartner

        try:
            partner_profile = DeliveryPartner.objects.get(user=order.delivery_partner)
            partner_profile.wallet_balance += order.delivery_fee
            partner_profile.save(update_fields=['wallet_balance', 'updated_at'])
        except DeliveryPartner.DoesNotExist:
            pass

    def _award_loyalty(self, order):
        if order.total <= 0:
            return
        try:
            EarnLoyaltyPointsAction.execute(
                user=order.customer,
                order_total=order.total,
                reference_id=str(order.pk),
                description=f'Earned points for order {order.order_number}',
            )
        except Exception as exc:
            logger.warning('Loyalty earn failed for order %s: %s', order.order_number, exc)
