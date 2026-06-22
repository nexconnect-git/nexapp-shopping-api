import json
from collections import defaultdict
from decimal import Decimal
from typing import List

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.renderers import JSONRenderer

from accounts.actions.loyalty_actions import EarnLoyaltyPointsAction, RedeemLoyaltyPointsAction, RUPEE_VALUE_PER_POINT, MAX_POINTS_REDEMPTION_PCT
from accounts.actions.wallet_actions import CreditWalletAction, DebitWalletAction
from accounts.models import Address
from backend.events import issue_message_added, order_cancelled, order_placed, order_status_updated
from helpers.delivery_quotes import DeliveryServiceabilityError, FarDeliveryConfirmationRequired, quote_vendor_delivery
from helpers.vendor_hours import get_vendor_availability
from notifications.models import Notification
from orders.actions.checkout import (
    COD_UPI_CONFIRMATION_MESSAGE,
    decimal_money,
    public_price_breakup,
    validate_cod_confirmation,
    validate_delivery_address,
    validate_schedule_slot,
    validate_single_vendor_cart,
    validate_vendor_minimum_order,
)
from orders.actions.refund_actions import IssueRazorpayRefundAction
from orders.models import (
    Cart,
    Coupon,
    CouponUsage,
    InventoryReservation,
    IssueMessage,
    Order,
    OrderIssue,
    OrderItem,
    OrderTracking,
)
from orders.serializers import IssueMessageSerializer
from products.actions.inventory import DecreaseStockAction
from products.data.product_repository import ProductRepository
from products.models import Product
from vendors.realtime import broadcast_order_event

from orders.actions.base import BaseAction


class CreateOrdersFromCartAction(BaseAction):
    @transaction.atomic
    def execute(self, user, delivery_address_id, payment_method="cod", notes="", coupon_code="", wallet_amount: Decimal = Decimal("0"), loyalty_points: int = 0, scheduled_for=None, confirm_far_delivery: bool = False, cod_upi_confirmed: bool = False, client_price_breakup: dict | None = None, client_idempotency_key: str = "") -> List[Order]:
        if not user.is_active:
            raise ValueError("Your account is not active. Please contact support.")
        client_idempotency_key = (client_idempotency_key or "").strip()[:120]
        if client_idempotency_key:
            existing_orders = list(
                Order.objects.select_for_update()
                .filter(customer=user, client_idempotency_key=client_idempotency_key)
                .select_related("vendor")
                .prefetch_related("items", "tracking")
                .order_by("placed_at")
            )
            if existing_orders:
                return existing_orders

        try:
            delivery_address = Address.objects.get(pk=delivery_address_id, user=user)
        except Address.DoesNotExist:
            raise ValueError("Delivery address not found.")
        validate_delivery_address(delivery_address)
        validate_cod_confirmation(payment_method, cod_upi_confirmed)

        try:
            cart = Cart.objects.select_for_update().get(user=user)
        except Cart.DoesNotExist:
            raise ValueError("Cart is empty.")

        cart_items = list(cart.items.select_related("product__vendor", "product__catalog_product").all())
        if not cart_items:
            raise ValueError("Cart is empty.")

        locked_products = {
            product.id: product
            for product in Product.objects.select_for_update(of=("self",))
            .select_related("vendor", "catalog_product")
            .filter(id__in=[item.product_id for item in cart_items])
        }
        for item in cart_items:
            product = locked_products.get(item.product_id)
            if not product:
                raise ValueError("One or more cart products are no longer available.")
            if not self._is_orderable_product(product):
                raise ValueError(f"'{product.name}' is no longer available for ordering.")
            item.product = product

        coupon = None
        if coupon_code:
            now = timezone.now()
            try:
                coupon = Coupon.objects.select_for_update().get(code=coupon_code, is_active=True)
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
        validate_single_vendor_cart(vendor_items)
        validate_vendor_minimum_order(vendor_items)

        vendor_quotes = {}
        confirmation_quotes = []

        cart_total = sum(
            item.product.price * item.quantity
            for items in vendor_items.values()
            for item in items
        )
        if coupon and cart_total < coupon.min_order_amount:
            raise ValueError(f"Minimum order amount for this coupon is {coupon.min_order_amount}.")

        from vendors.models import VendorHoliday

        now_local = timezone.localtime(timezone.now())
        today = now_local.date()

        for vendor in vendor_items:
            is_open_now, availability_note = get_vendor_availability(vendor, current_dt=now_local)
            if not scheduled_for and not is_open_now:
                raise ValueError(f"'{vendor.store_name}' {availability_note.lower()}.")
            if not scheduled_for and VendorHoliday.objects.filter(vendor=vendor, date=today).exists():
                raise ValueError(f"'{vendor.store_name}' is closed today for a holiday.")
            validate_schedule_slot(scheduled_for, vendor, vendor_items[vendor])

        total_coupon_discount = coupon.calculate_discount(cart_total) if coupon else Decimal("0")

        wallet_amount = max(Decimal("0"), wallet_amount)
        if wallet_amount > Decimal("0"):
            from accounts.models.wallet import Wallet

            try:
                wallet_balance = Wallet.objects.get(user=user).balance
            except Wallet.DoesNotExist:
                wallet_balance = Decimal("0")
            if wallet_amount > wallet_balance:
                raise ValueError(
                    f"Insufficient wallet balance. Available: {wallet_balance}, Requested: {wallet_amount}"
                )

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
            loyalty_points = int(loyalty_discount / RUPEE_VALUE_PER_POINT)

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
            quote = quote_vendor_delivery(
                vendor=vendor,
                address=delivery_address,
                products=[item.product for item in items],
                quantities={str(item.product.id): item.quantity for item in items},
                subtotal=subtotal,
                platform=platform,
            )
            vendor_quotes[vendor.id] = quote

            if not quote.is_serviceable:
                raise DeliveryServiceabilityError(quote)

            if quote.requires_far_delivery_confirmation and not confirm_far_delivery:
                confirmation_quotes.append(quote.as_dict())

        if confirmation_quotes and not confirm_far_delivery:
            raise FarDeliveryConfirmationRequired(confirmation_quotes)

        for vendor, items in vendor_items.items():
            subtotal = sum(item.product.price * item.quantity for item in items)
            quote = vendor_quotes[vendor.id]

            delivery_fee = quote.delivery_fee
            if platform.free_delivery_above > 0 and subtotal >= platform.free_delivery_above:
                delivery_fee = Decimal("0")
            if coupon and coupon.discount_type == "free_delivery":
                delivery_fee = Decimal("0")

            vendor_discount = (
                (subtotal / cart_total * total_coupon_discount).quantize(Decimal("0.01"))
                if cart_total else Decimal("0")
            )
            pre_wallet_total = subtotal + delivery_fee - vendor_discount
            vendor_wallet_share = (
                (subtotal / cart_total * wallet_amount).quantize(Decimal("0.01"))
                if cart_total and wallet_amount > Decimal("0") else Decimal("0")
            )
            vendor_loyalty_share = (
                (subtotal / cart_total * loyalty_discount).quantize(Decimal("0.01"))
                if cart_total and loyalty_discount > Decimal("0") else Decimal("0")
            )
            product_discount = sum(
                max((item.product.compare_price or item.product.price) - item.product.price, Decimal("0")) * item.quantity
                for item in items
            ).quantize(Decimal("0.01"))
            platform_fee = decimal_money(getattr(platform, "platform_fee", 0))
            packaging_fee = decimal_money(getattr(platform, "packaging_fee", 0))
            small_cart_threshold = decimal_money(getattr(platform, "small_cart_threshold", 0))
            small_cart_fee = decimal_money(getattr(platform, "small_cart_fee", 0)) if small_cart_threshold and subtotal < small_cart_threshold else Decimal("0.00")
            surge_fee = decimal_money(getattr(platform, "surge_fee", 0))
            tax_rate = decimal_money(getattr(platform, "tax_percentage", 0))
            taxable = max(subtotal - vendor_discount, Decimal("0.00")) + platform_fee + packaging_fee + small_cart_fee + surge_fee
            tax_amount = (taxable * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
            total = max(
                pre_wallet_total - vendor_wallet_share - vendor_loyalty_share + platform_fee + packaging_fee + small_cart_fee + surge_fee + tax_amount,
                Decimal("0"),
            ).quantize(Decimal("0.01"))
            price_preview = {
                "item_subtotal": subtotal.quantize(Decimal("0.01")),
                "product_discount": product_discount,
                "coupon_discount": vendor_discount,
                "delivery_fee": delivery_fee,
                "platform_fee": platform_fee,
                "packaging_fee": packaging_fee,
                "small_cart_fee": small_cart_fee,
                "tax_amount": tax_amount,
                "surge_fee": surge_fee,
                "wallet_discount": vendor_wallet_share,
                "loyalty_discount": vendor_loyalty_share,
                "final_payable": total,
                "free_delivery_above": platform.free_delivery_above,
            }

            order = Order.objects.create(
                customer=user,
                vendor=vendor,
                delivery_address=delivery_address,
                payment_method=payment_method,
                subtotal=subtotal,
                product_discount=product_discount,
                delivery_fee=delivery_fee,
                platform_fee=platform_fee,
                packaging_fee=packaging_fee,
                small_cart_fee=small_cart_fee,
                tax_amount=tax_amount,
                surge_fee=surge_fee,
                coupon=coupon,
                coupon_discount=vendor_discount,
                wallet_discount=vendor_wallet_share,
                loyalty_discount=vendor_loyalty_share,
                discount=(vendor_discount + vendor_wallet_share + vendor_loyalty_share).quantize(Decimal("0.01")),
                total=total,
                notes=notes,
                scheduled_for=scheduled_for,
                estimated_delivery_time=quote.estimated_delivery_minutes,
                delivery_latitude=delivery_address.latitude,
                delivery_longitude=delivery_address.longitude,
                client_idempotency_key=client_idempotency_key,
                price_breakup=public_price_breakup(price_preview),
                payment_metadata={
                    "cod_upi_confirmed": bool(cod_upi_confirmed),
                    "cod_upi_message": COD_UPI_CONFIRMATION_MESSAGE if payment_method == "cod" else "",
                    "client_price_breakup": client_price_breakup or {},
                },
            )

            for item in items:
                reservation = InventoryReservation.objects.create(
                    cart=cart,
                    order=order,
                    product=item.product,
                    vendor=item.product.vendor,
                    quantity=item.quantity,
                    price_at_reservation=item.product.price,
                    reserved_until=InventoryReservation.default_expiry(),
                )
                order_item = OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    catalog_product=item.product.catalog_product,
                    vendor=item.product.vendor,
                    product_name=item.product.name,
                    product_brand=item.product.brand,
                    product_unit=item.product.unit,
                    product_pack_size=item.product.weight,
                    product_sku=item.product.sku,
                    product_slug=item.product.slug,
                    product_price=item.product.price,
                    product_compare_price=item.product.compare_price,
                    quantity=item.quantity,
                    subtotal=item.product.price * item.quantity,
                )
                decrease_stock.execute(str(item.product.pk), item.quantity)
                reservation.order_item = order_item
                reservation.save(update_fields=["order_item", "updated_at"])
                reservation.commit()

            OrderTracking.objects.create(order=order, status="placed", description="Order has been placed.")
            if vendor.auto_order_acceptance:
                old_status = order.status
                order.status = "confirmed"
                order.save(update_fields=["status", "updated_at"])
                OrderTracking.objects.create(
                    order=order,
                    status="confirmed",
                    description="Order auto-accepted by vendor settings.",
                )
                Notification.objects.create(
                    user=order.customer,
                    title="Order Confirmed",
                    message="Your order has been automatically confirmed by the vendor.",
                    notification_type="order",
                    data={"order_id": str(order.id), "order_number": order.order_number},
                )
                broadcast_order_event(order, "order_updated")
            created_orders.append(order)

        if coupon and created_orders:
            for order in created_orders:
                CouponUsage.objects.create(
                    coupon=coupon,
                    user=user,
                    order=order,
                    discount_applied=order.coupon_discount,
                )
            updated = Coupon.objects.filter(
                pk=coupon.pk,
            ).filter(
                Q(usage_limit__isnull=True) | Q(used_count__lt=F("usage_limit"))
            ).update(used_count=F("used_count") + 1)
            if not updated:
                raise ValueError("Coupon usage limit reached.")

        cart.items.all().delete()

        if wallet_amount > Decimal("0") and created_orders:
            order_refs = ", ".join(o.order_number for o in created_orders)
            DebitWalletAction.execute(
                user=user,
                amount=wallet_amount,
                source="order_payment",
                reference_id=str(created_orders[0].pk),
                description=f"Wallet payment for order(s) {order_refs}",
            )

        if loyalty_points > 0 and created_orders:
            order_refs = ", ".join(o.order_number for o in created_orders)
            RedeemLoyaltyPointsAction.execute(
                user=user,
                points_to_redeem=loyalty_points,
                reference_id=str(created_orders[0].pk),
                description=f"Redeemed {loyalty_points} pts for order(s) {order_refs}",
            )

        try:
            from accounts.models.referral import REFERRAL_BONUS_POINTS, Referral

            referral = Referral.objects.filter(referee=user, bonus_awarded=False).select_related("referrer").first()
            if referral and not Order.objects.filter(customer=user).exclude(pk__in=[o.pk for o in created_orders]).exists():
                EarnLoyaltyPointsAction.execute(
                    user=referral.referrer,
                    order_total=0,
                    reference_id=str(created_orders[0].pk),
                    description=f"Referral bonus: {user.username} placed their first order",
                )
                from accounts.models.loyalty import LoyaltyAccount, LoyaltyTransaction

                account = LoyaltyAccount.objects.get_or_create(user=referral.referrer)[0]
                account.points = account.points - 1 + REFERRAL_BONUS_POINTS
                account.lifetime_points = account.lifetime_points - 1 + REFERRAL_BONUS_POINTS
                account.save(update_fields=["points", "lifetime_points", "updated_at"])
                LoyaltyTransaction.objects.filter(
                    account=account,
                    reference_id=str(created_orders[0].pk),
                    points=1,
                ).update(
                    points=REFERRAL_BONUS_POINTS,
                    description=f"Referral bonus: {user.username}'s first order",
                )
                referral.bonus_awarded = True
                referral.save(update_fields=["bonus_awarded"])
        except Exception:
            pass

        for order in created_orders:
            order_placed.send(sender=Order, order=order)

        return created_orders

    def _is_orderable_product(self, product) -> bool:
        return (
            product.approval_status == ProductRepository.CUSTOMER_VISIBLE_FILTERS["approval_status"]
            and product.status == ProductRepository.CUSTOMER_VISIBLE_FILTERS["status"]
            and product.is_available == ProductRepository.CUSTOMER_VISIBLE_FILTERS["is_available"]
            and bool(product.catalog_product_id)
        )
