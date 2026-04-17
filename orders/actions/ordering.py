import json
from collections import defaultdict
from decimal import Decimal
from typing import List

from django.db import transaction
from django.utils import timezone
from rest_framework.renderers import JSONRenderer

from accounts.models import Address
from accounts.actions.wallet_actions import DebitWalletAction, CreditWalletAction
from accounts.actions.loyalty_actions import EarnLoyaltyPointsAction, RedeemLoyaltyPointsAction, RUPEE_VALUE_PER_POINT, MAX_POINTS_REDEMPTION_PCT
from backend.events import order_cancelled, order_placed, order_status_updated, issue_message_added
from backend.utils import haversine
from orders.models import (
    Cart, Coupon, CouponUsage, IssueMessage, Order, OrderIssue,
    OrderItem, OrderTracking,
)
from orders.serializers import IssueMessageSerializer
from products.actions.inventory import DecreaseStockAction
from orders.actions.refund_actions import IssueRazorpayRefundAction
from .base import BaseAction


class CreateOrdersFromCartAction(BaseAction):
    @transaction.atomic
    def execute(self, user, delivery_address_id, payment_method="cod", notes="", coupon_code="", wallet_amount: Decimal = Decimal("0"), loyalty_points: int = 0, scheduled_for=None) -> List[Order]:
        try:
            delivery_address = Address.objects.get(pk=delivery_address_id, user=user)
        except Address.DoesNotExist:
            raise ValueError("Delivery address not found.")

        try:
            cart = Cart.objects.prefetch_related("items__product__vendor").get(user=user)
        except Cart.DoesNotExist:
            raise ValueError("Cart is empty.")

        cart_items = cart.items.select_related("product__vendor").all()
        if not cart_items.exists():
            raise ValueError("Cart is empty.")

        coupon = None
        if coupon_code:
            now = timezone.now()
            try:
                coupon = Coupon.objects.get(code=coupon_code, is_active=True)
                if coupon.valid_until and coupon.valid_until < now:
                    raise ValueError("Coupon has expired.")
                if coupon.valid_from > now:
                    raise ValueError("Coupon is not yet valid.")
                if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
                    raise ValueError("Coupon usage limit reached.")
                user_uses = CouponUsage.objects.filter(coupon=coupon, user=user).count()
                if user_uses >= coupon.per_user_limit:
                    raise ValueError("You have already used this coupon.")
            except Coupon.DoesNotExist:
                raise ValueError("Invalid coupon code.")

        vendor_items: dict = defaultdict(list)
        for item in cart_items:
            vendor_items[item.product.vendor].append(item)

        cart_total = sum(
            item.product.price * item.quantity
            for items in vendor_items.values()
            for item in items
        )
        if coupon and cart_total < coupon.min_order_amount:
            raise ValueError(f"Minimum order amount for this coupon is {coupon.min_order_amount}.")

        # Validate vendor operating hours and holidays
        from vendors.models import VendorHoliday
        now_local = timezone.localtime(timezone.now())
        today = now_local.date()
        current_time = now_local.time()

        for vendor in vendor_items:
            if not vendor.is_open:
                raise ValueError(f"'{vendor.store_name}' is currently closed.")
            if vendor.opening_time and vendor.closing_time:
                if not (vendor.opening_time <= current_time <= vendor.closing_time):
                    raise ValueError(
                        f"'{vendor.store_name}' is closed right now. "
                        f"Open {vendor.opening_time.strftime('%H:%M')} – "
                        f"{vendor.closing_time.strftime('%H:%M')}."
                    )
            if VendorHoliday.objects.filter(vendor=vendor, date=today).exists():
                raise ValueError(f"'{vendor.store_name}' is closed today for a holiday.")

        total_coupon_discount = coupon.calculate_discount(cart_total) if coupon else Decimal("0")

        # Validate wallet amount
        wallet_amount = max(Decimal("0"), wallet_amount)
        if wallet_amount > Decimal("0"):
            from accounts.models.wallet import Wallet
            try:
                wallet_balance = Wallet.objects.get(user=user).balance
            except Wallet.DoesNotExist:
                wallet_balance = Decimal("0")
            if wallet_amount > wallet_balance:
                raise ValueError(
                    f"Insufficient wallet balance. Available: ₹{wallet_balance}, Requested: ₹{wallet_amount}"
                )

        # Validate loyalty points redemption
        loyalty_points = max(0, int(loyalty_points))
        loyalty_discount = Decimal("0")
        if loyalty_points > 0:
            from accounts.models.loyalty import LoyaltyAccount
            try:
                loyalty_account = LoyaltyAccount.objects.get(user=user)
            except LoyaltyAccount.DoesNotExist:
                loyalty_account = None
            available_points = loyalty_account.points if loyalty_account else 0
            if loyalty_points > available_points:
                raise ValueError(
                    f"Insufficient loyalty points. Available: {available_points}, Requested: {loyalty_points}"
                )
            max_discount = (cart_total * MAX_POINTS_REDEMPTION_PCT / 100).quantize(Decimal("0.01"))
            loyalty_discount = min(
                Decimal(str(loyalty_points)) * RUPEE_VALUE_PER_POINT,
                max_discount,
            ).quantize(Decimal("0.01"))
            # Recalculate actual points to redeem based on capped discount
            loyalty_points = int(loyalty_discount / RUPEE_VALUE_PER_POINT)

        # Pre-check stock for all items before creating any orders
        for item in cart_items:
            if item.product.stock < item.quantity:
                available = item.product.stock
                raise ValueError(
                    f"'{item.product.name}' only has {available} unit(s) in stock "
                    f"but {item.quantity} requested."
                )

        from orders.models.setting import PlatformSetting
        platform = PlatformSetting.get_setting()

        created_orders: List[Order] = []
        decrease_stock = DecreaseStockAction()

        for vendor, items in vendor_items.items():
            subtotal = sum(item.product.price * item.quantity for item in items)

            distance = 0
            if delivery_address.latitude and delivery_address.longitude:
                distance = haversine(
                    float(vendor.latitude), float(vendor.longitude),
                    float(delivery_address.latitude), float(delivery_address.longitude),
                )

            if coupon and coupon.discount_type == "free_delivery":
                delivery_fee = Decimal("0")
            elif platform.free_delivery_above > 0 and subtotal >= platform.free_delivery_above:
                delivery_fee = Decimal("0")
            else:
                delivery_fee = (
                    platform.delivery_base_fee
                    + platform.delivery_per_km_fee * Decimal(str(round(distance, 2)))
                )

            vendor_discount = (
                (subtotal / cart_total * total_coupon_discount).quantize(Decimal("0.01"))
                if cart_total else Decimal("0")
            )
            pre_wallet_total = subtotal + delivery_fee - vendor_discount
            # Distribute wallet discount proportionally by vendor subtotal share
            vendor_wallet_share = (
                (subtotal / cart_total * wallet_amount).quantize(Decimal("0.01"))
                if cart_total and wallet_amount > Decimal("0") else Decimal("0")
            )
            vendor_loyalty_share = (
                (subtotal / cart_total * loyalty_discount).quantize(Decimal("0.01"))
                if cart_total and loyalty_discount > Decimal("0") else Decimal("0")
            )
            total = max(pre_wallet_total - vendor_wallet_share - vendor_loyalty_share, Decimal("0"))

            order = Order.objects.create(
                customer=user, vendor=vendor, delivery_address=delivery_address,
                payment_method=payment_method, subtotal=subtotal, delivery_fee=delivery_fee,
                coupon=coupon, coupon_discount=vendor_discount,
                wallet_discount=vendor_wallet_share,
                total=total, notes=notes,
                scheduled_for=scheduled_for,
                delivery_latitude=delivery_address.latitude,
                delivery_longitude=delivery_address.longitude,
            )

            for item in items:
                OrderItem.objects.create(
                    order=order, product=item.product,
                    product_name=item.product.name, product_price=item.product.price,
                    quantity=item.quantity, subtotal=item.product.price * item.quantity,
                )
                decrease_stock.execute(str(item.product.pk), item.quantity)

            OrderTracking.objects.create(order=order, status="placed", description="Order has been placed.")
            created_orders.append(order)

        if coupon and created_orders:
            for order in created_orders:
                CouponUsage.objects.create(
                    coupon=coupon, user=user, order=order, discount_applied=order.coupon_discount,
                )
            Coupon.objects.filter(pk=coupon.pk).update(used_count=coupon.used_count + 1)

        cart.items.all().delete()

        # Debit wallet once for the full wallet_amount used
        if wallet_amount > Decimal("0") and created_orders:
            order_refs = ", ".join(o.order_number for o in created_orders)
            DebitWalletAction.execute(
                user=user,
                amount=wallet_amount,
                source='order_payment',
                reference_id=str(created_orders[0].pk),
                description=f"Wallet payment for order(s) {order_refs}",
            )

        # Redeem loyalty points once for the full redemption
        if loyalty_points > 0 and created_orders:
            order_refs = ", ".join(o.order_number for o in created_orders)
            RedeemLoyaltyPointsAction.execute(
                user=user,
                points_to_redeem=loyalty_points,
                reference_id=str(created_orders[0].pk),
                description=f"Redeemed {loyalty_points} pts for order(s) {order_refs}",
            )

        for order in created_orders:
            order_placed.send(sender=Order, order=order)

        return created_orders


class CancelOrderAction(BaseAction):
    @transaction.atomic
    def execute(self, order_id, user) -> Order:
        try:
            order = Order.objects.get(pk=order_id, customer=user)
        except Order.DoesNotExist:
            raise ValueError("Order not found.")

        # Customers may cancel up to and including "ready" (before dispatch)
        customer_allowed = ["placed", "confirmed", "preparing", "ready"]
        if order.status not in customer_allowed:
            if order.status == "delivered":
                raise ValueError("Delivered orders cannot be cancelled.")
            raise ValueError(
                "Orders that are already dispatched or delivered cannot be cancelled. "
                "Please contact support."
            )

        from orders.models.setting import PlatformSetting
        setting = PlatformSetting.get_setting()
        if setting.cancellation_window_minutes > 0:
            elapsed_minutes = (timezone.now() - order.placed_at).total_seconds() / 60
            if elapsed_minutes > setting.cancellation_window_minutes:
                raise ValueError(
                    f"Orders can only be cancelled within {setting.cancellation_window_minutes} "
                    f"minutes of placement. This order was placed "
                    f"{int(elapsed_minutes)} minutes ago."
                )

        order.status = "cancelled"
        order.save(update_fields=["status", "updated_at"])
        OrderTracking.objects.create(order=order, status="cancelled", description="Order cancelled by customer.")

        # Restore stock for each item
        from products.models import Product as ProductModel
        for item in order.items.select_related("product").all():
            if item.product:
                ProductModel.objects.filter(pk=item.product.pk).update(
                    stock=item.product.stock + item.quantity,
                )
                # Re-activate if it was sold_out and now has stock
                if item.product.status == "sold_out":
                    ProductModel.objects.filter(pk=item.product.pk).update(status="active")

        # Refund wallet discount if any was applied
        if order.wallet_discount > Decimal("0"):
            try:
                CreditWalletAction.execute(
                    user=order.customer,
                    amount=order.wallet_discount,
                    source='refund',
                    reference_id=str(order.pk),
                    description=f"Wallet refund for cancelled order {order.order_number}",
                )
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "Wallet refund failed for order %s: %s", order.order_number, exc
                )

        # Issue Razorpay refund if order was paid online
        if order.payment_method == 'razorpay' and order.is_payment_verified and not order.razorpay_refund_id:
            try:
                IssueRazorpayRefundAction().execute(order)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "Refund failed for order %s: %s", order.order_number, exc
                )

        order_cancelled.send(sender=Order, order=order)
        return order


class AdminUpdateOrderStatusAction(BaseAction):
    @transaction.atomic
    def execute(self, order_id, new_status, admin_user) -> Order:
        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            raise ValueError("Order not found.")

        valid_statuses = ["placed", "confirmed", "preparing", "ready", "picked_up", "on_the_way", "delivered", "cancelled"]
        if new_status not in valid_statuses:
            raise ValueError("Invalid status.")

        if new_status == "cancelled" and order.status == "delivered":
            raise ValueError("Delivered orders cannot be cancelled.")

        old_status = order.status
        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

        # Issue Razorpay refund when admin cancels a paid online order
        if new_status == "cancelled" and order.payment_method == 'razorpay' \
                and order.is_payment_verified and not order.razorpay_refund_id:
            try:
                IssueRazorpayRefundAction().execute(order)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "Admin cancel refund failed for order %s: %s", order.order_number, exc
                )
        OrderTracking.objects.create(order=order, status=new_status, description=f"Status updated by admin to {new_status}.")
        order_status_updated.send(sender=Order, order=order, new_status=new_status, old_status=old_status)

        if new_status == "delivered" and old_status != "delivered":
            with transaction.atomic():
                vendor = order.vendor
                vendor_earnings = order.subtotal - order.coupon_discount
                
                from vendors.actions.wallet_actions import VendorWalletAction
                VendorWalletAction.credit_vendor(
                    vendor_id=str(vendor.id),
                    amount=vendor_earnings,
                    source='order_earning',
                    reference_id=str(order.id),
                    description=f"Earnings from Order #{order.order_number}"
                )

                if order.delivery_partner:
                    from delivery.models import DeliveryPartner
                    try:
                        partner_profile = DeliveryPartner.objects.get(user=order.delivery_partner)
                        partner_profile.wallet_balance += order.delivery_fee
                        partner_profile.save(update_fields=["wallet_balance", "updated_at"])
                    except DeliveryPartner.DoesNotExist:
                        pass

                # Award loyalty points to customer based on amount actually paid
                paid_amount = order.total
                if paid_amount > 0:
                    try:
                        EarnLoyaltyPointsAction.execute(
                            user=order.customer,
                            order_total=paid_amount,
                            reference_id=str(order.pk),
                            description=f"Earned points for order {order.order_number}",
                        )
                    except Exception as exc:
                        import logging as _logging
                        _logging.getLogger(__name__).warning(
                            "Loyalty earn failed for order %s: %s", order.order_number, exc
                        )

        return order


class AddIssueMessageAction(BaseAction):
    @transaction.atomic
    def execute(self, issue_id, user, message_text) -> dict:
        is_admin = user.role == "admin"
        try:
            if is_admin:
                issue = OrderIssue.objects.get(id=issue_id)
            else:
                issue = OrderIssue.objects.get(id=issue_id, customer=user)
        except OrderIssue.DoesNotExist:
            raise ValueError("Issue not found.")

        issue_message = IssueMessage.objects.create(
            issue=issue, sender=user, is_admin=is_admin, message=message_text,
        )

        if issue.status == "open" and not is_admin:
            issue.status = "in_review"
            issue.save(update_fields=["status", "updated_at"])

        serializer = IssueMessageSerializer(issue_message)
        message_data = json.loads(JSONRenderer().render(serializer.data).decode("utf-8"))
        issue_message_added.send(sender=IssueMessage, issue_id=issue.id, message_data=message_data)
        return serializer.data
