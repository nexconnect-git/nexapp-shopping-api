import json
from collections import defaultdict
from decimal import Decimal
from typing import List

from django.db import transaction
from django.utils import timezone
from rest_framework.renderers import JSONRenderer

from accounts.models import Address
from backend.events import order_cancelled, order_placed, order_status_updated, issue_message_added
from backend.utils import haversine
from orders.models import (
    Cart, Coupon, CouponUsage, IssueMessage, Order, OrderIssue,
    OrderItem, OrderTracking,
)
from orders.serializers import IssueMessageSerializer
from products.actions.inventory import DecreaseStockAction
from .base import BaseAction


class CreateOrdersFromCartAction(BaseAction):
    @transaction.atomic
    def execute(self, user, delivery_address_id, payment_method="cod", notes="", coupon_code="") -> List[Order]:
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

        total_coupon_discount = coupon.calculate_discount(cart_total) if coupon else Decimal("0")
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
            delivery_fee = Decimal("30") + Decimal("5") * Decimal(str(round(distance, 2)))
            if coupon and coupon.discount_type == "free_delivery":
                delivery_fee = Decimal("0")

            vendor_discount = (
                (subtotal / cart_total * total_coupon_discount).quantize(Decimal("0.01"))
                if cart_total else Decimal("0")
            )
            total = subtotal + delivery_fee - vendor_discount

            order = Order.objects.create(
                customer=user, vendor=vendor, delivery_address=delivery_address,
                payment_method=payment_method, subtotal=subtotal, delivery_fee=delivery_fee,
                coupon=coupon, coupon_discount=vendor_discount,
                total=max(total, Decimal("0")), notes=notes,
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

        if order.status in ["picked_up", "on_the_way", "delivered"]:
            raise ValueError("Order can't be cancelled because it is dispatched.")

        order.status = "cancelled"
        order.save(update_fields=["status", "updated_at"])
        OrderTracking.objects.create(order=order, status="cancelled", description="Order cancelled by customer.")
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

        if new_status == "cancelled" and order.status in ["picked_up", "on_the_way", "delivered"]:
            raise ValueError("Order can't be cancelled because it is dispatched.")

        old_status = order.status
        order.status = new_status
        order.save(update_fields=["status", "updated_at"])
        OrderTracking.objects.create(order=order, status=new_status, description=f"Status updated by admin to {new_status}.")
        order_status_updated.send(sender=Order, order=order, new_status=new_status, old_status=old_status)

        if new_status == "delivered" and old_status != "delivered":
            with transaction.atomic():
                vendor = order.vendor
                vendor_earnings = order.subtotal - order.coupon_discount
                vendor.wallet_balance += vendor_earnings
                vendor.save(update_fields=["wallet_balance", "updated_at"])

                if order.delivery_partner:
                    from delivery.models import DeliveryPartner
                    try:
                        partner_profile = DeliveryPartner.objects.get(user=order.delivery_partner)
                        partner_profile.wallet_balance += order.delivery_fee
                        partner_profile.save(update_fields=["wallet_balance", "updated_at"])
                    except DeliveryPartner.DoesNotExist:
                        pass

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
