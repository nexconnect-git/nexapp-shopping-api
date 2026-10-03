import logging
from decimal import Decimal

from django.db import transaction

from accounts.actions.wallet_actions import CreditWalletAction
from delivery.data.assignment_repo import DeliveryAssignmentRepository
from delivery.data.partner_repo import DeliveryPartnerRepository
from notifications.data.notification_repository import NotificationRepository
from orders.actions.inventory_reservations import ReservationInventoryAction
from orders.actions.refund_actions import IssueRazorpayRefundAction
from orders.data.order_repo import OrderRepository


logger = logging.getLogger(__name__)


class OrderCancellationEffectsAction:
    @transaction.atomic
    def execute(self, order):
        order = OrderRepository.get_locked(order.pk)
        if order.status != 'cancelled':
            raise ValueError('Cancellation effects require a cancelled order.')
        assignment = DeliveryAssignmentRepository.get_locked_for_order(order)
        if assignment:
            assignment.status = 'cancelled'
            assignment.accepted_partner = None
            assignment.save(update_fields=['status', 'accepted_partner', 'updated_at'])
            assignment.notified_partners.clear()
            assignment.rejected_partners.clear()
            NotificationRepository().filter(
                notification_type='delivery', data__assignment_id=str(assignment.pk),
                data__type='assignment_request',
            ).delete()
        if order.delivery_partner_id:
            partner = DeliveryPartnerRepository.get_locked_by_user(order.delivery_partner)
            partner.status = 'on_delivery' if OrderRepository.has_active_deliveries(partner.user) else 'available'
            partner.save(update_fields=['status', 'updated_at'])
        ReservationInventoryAction().release_order(order, reason='cancelled')
        if order.wallet_discount > Decimal('0'):
            CreditWalletAction.execute(
                user=order.customer, amount=order.wallet_discount, source='refund',
                reference_id=str(order.pk), description=f'Wallet refund for cancelled order {order.order_number}',
            )
        if order.payment_method == 'razorpay' and order.is_payment_verified and not order.razorpay_refund_id:
            try:
                IssueRazorpayRefundAction().execute(order)
            except Exception:
                logger.exception('Gateway refund failed for cancelled order %s.', order.order_number)
