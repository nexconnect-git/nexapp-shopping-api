from decimal import Decimal

from django.db import transaction

from accounts.actions.loyalty_actions import EarnLoyaltyPointsAction
from delivery.data.earning_repo import DeliveryEarningRepository
from delivery.data.partner_repo import DeliveryPartnerRepository
from orders.data.order_repo import OrderRepository
from vendors.actions.wallet_actions import VendorWalletAction


class SettleDeliveredOrderAction:
    @transaction.atomic
    def execute(self, order):
        order = OrderRepository.get_locked(order.pk)
        if order.status != 'delivered':
            raise ValueError('Only delivered orders can be settled.')
        vendor_earnings = order.subtotal - order.coupon_discount
        if vendor_earnings > Decimal('0'):
            VendorWalletAction.credit_vendor(
                vendor_id=str(order.vendor_id), amount=vendor_earnings, source='order_earning',
                reference_id=str(order.pk), description=f'Earnings from order {order.order_number}',
            )
        if order.delivery_partner_id:
            partner = DeliveryPartnerRepository.get_locked_by_user(order.delivery_partner)
            _earning, created = DeliveryEarningRepository.get_or_create(partner, order, order.delivery_fee)
            if created:
                partner.wallet_balance += order.delivery_fee
                partner.total_deliveries += 1
                partner.total_earnings += order.delivery_fee
            partner.status = 'on_delivery' if OrderRepository.has_active_deliveries(partner.user) else 'available'
            partner.save(update_fields=['wallet_balance', 'total_deliveries', 'total_earnings', 'status', 'updated_at'])
        if order.total > 0:
            EarnLoyaltyPointsAction.execute(
                user=order.customer, order_total=order.total, reference_id=str(order.pk),
                description=f'Earned points for order {order.order_number}',
            )
