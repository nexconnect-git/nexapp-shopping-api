"""Service layer for the orders app.

Contains the core order lifecycle logic: cart-to-order conversion, order
cancellation, status updates, and issue messaging.  All mutating operations
use database transactions to guarantee consistency.
"""

import json
from collections import defaultdict
from decimal import Decimal
from typing import List

from django.db import transaction
from django.utils import timezone
from rest_framework.renderers import JSONRenderer

from accounts.models import Address, User
from backend.events import (
    issue_message_added,
    order_cancelled,
    order_placed,
    order_status_updated,
)
from backend.utils import haversine
from orders.models import (
    Cart,
    Coupon,
    CouponUsage,
    IssueMessage,
    Order,
    OrderIssue,
    OrderItem,
    OrderTracking,
)
from orders.serializers import IssueMessageSerializer
from products.services import ProductService


class OrderService:
    """Stateless service class for order-related business operations."""

    @staticmethod
    @transaction.atomic
    def create_orders_from_cart(
        user: User,
        delivery_address_id: str,
        payment_method: str = "cod",
        notes: str = "",
        coupon_code: str = "",
    ) -> List[Order]:
        """Convert the user's cart into one or more vendor-specific orders.

        Groups cart items by vendor, applies any coupon discount proportionally,
        calculates delivery fees using the Haversine formula, decrements stock,
        and fires the ``order_placed`` signal for each created order.

        Args:
            user: The customer placing the order.
            delivery_address_id: UUID of the ``Address`` to deliver to.
            payment_method: Payment method string (default ``"cod"``).
            notes: Optional order notes supplied by the customer.
            coupon_code: Optional coupon code to apply.

        Returns:
            A list of newly created ``Order`` instances (one per vendor).

        Raises:
            ValueError: For invalid/empty cart, bad address, expired/invalid
                coupon, or unmet coupon minimum order amount.
        """
        try:
            delivery_address = Address.objects.get(
                pk=delivery_address_id, user=user
            )
        except Address.DoesNotExist:
            raise ValueError("Delivery address not found.")

        try:
            cart = Cart.objects.prefetch_related(
                "items__product__vendor"
            ).get(user=user)
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
                user_uses = CouponUsage.objects.filter(
                    coupon=coupon, user=user
                ).count()
                if user_uses >= coupon.per_user_limit:
                    raise ValueError("You have already used this coupon.")
            except Coupon.DoesNotExist:
                raise ValueError("Invalid coupon code.")

        # Group items by vendor so we create one order per vendor
        vendor_items: dict = defaultdict(list)
        for item in cart_items:
            vendor_items[item.product.vendor].append(item)

        cart_total = sum(
            item.product.price * item.quantity
            for items in vendor_items.values()
            for item in items
        )
        if coupon and cart_total < coupon.min_order_amount:
            raise ValueError(
                f"Minimum order amount for this coupon is "
                f"{coupon.min_order_amount}."
            )

        total_coupon_discount = (
            coupon.calculate_discount(cart_total) if coupon else Decimal("0")
        )
        created_orders: List[Order] = []

        for vendor, items in vendor_items.items():
            subtotal = sum(item.product.price * item.quantity for item in items)

            # Calculate distance-based delivery fee
            distance = 0
            if delivery_address.latitude and delivery_address.longitude:
                distance = haversine(
                    float(vendor.latitude),
                    float(vendor.longitude),
                    float(delivery_address.latitude),
                    float(delivery_address.longitude),
                )
            delivery_fee = Decimal("30") + Decimal("5") * Decimal(
                str(round(distance, 2))
            )
            if coupon and coupon.discount_type == "free_delivery":
                delivery_fee = Decimal("0")

            # Distribute coupon discount proportionally across vendor sub-orders
            vendor_discount = (
                (subtotal / cart_total * total_coupon_discount).quantize(
                    Decimal("0.01")
                )
                if cart_total
                else Decimal("0")
            )
            total = subtotal + delivery_fee - vendor_discount

            order = Order.objects.create(
                customer=user,
                vendor=vendor,
                delivery_address=delivery_address,
                payment_method=payment_method,
                subtotal=subtotal,
                delivery_fee=delivery_fee,
                coupon=coupon,
                coupon_discount=vendor_discount,
                total=max(total, Decimal("0")),
                notes=notes,
                delivery_latitude=delivery_address.latitude,
                delivery_longitude=delivery_address.longitude,
            )

            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    product_name=item.product.name,
                    product_price=item.product.price,
                    quantity=item.quantity,
                    subtotal=item.product.price * item.quantity,
                )
                # Decrement stock atomically via service
                ProductService.decrease_stock(str(item.product.pk), item.quantity)

            OrderTracking.objects.create(
                order=order,
                status="placed",
                description="Order has been placed.",
            )
            created_orders.append(order)

        if coupon and created_orders:
            for order in created_orders:
                CouponUsage.objects.create(
                    coupon=coupon,
                    user=user,
                    order=order,
                    discount_applied=order.coupon_discount,
                )
            Coupon.objects.filter(pk=coupon.pk).update(
                used_count=coupon.used_count + 1
            )

        cart.items.all().delete()

        # Fire order_placed signal for notification and other side effects
        for order in created_orders:
            order_placed.send(sender=Order, order=order)

        return created_orders

    @staticmethod
    @transaction.atomic
    def cancel_order(order_id: str, user: User) -> Order:
        """Cancel an order on behalf of the customer.

        Args:
            order_id: UUID primary key of the order to cancel.
            user: The customer requesting the cancellation.

        Returns:
            The updated ``Order`` instance with status ``"cancelled"``.

        Raises:
            ValueError: If the order does not exist or is not in a
                cancellable state (``placed`` or ``confirmed``).
        """
        try:
            order = Order.objects.get(pk=order_id, customer=user)
        except Order.DoesNotExist:
            raise ValueError("Order not found.")

        if order.status not in ("placed", "confirmed"):
            raise ValueError(
                "Order can only be cancelled if placed or confirmed."
            )

        order.status = "cancelled"
        order.save(update_fields=["status", "updated_at"])

        OrderTracking.objects.create(
            order=order,
            status="cancelled",
            description="Order cancelled by customer.",
        )

        order_cancelled.send(sender=Order, order=order)
        return order

    @staticmethod
    @transaction.atomic
    def update_order_status(
        order_id: str, new_status: str, _admin_user: User
    ) -> Order:
        """Update an order's status (admin operation).

        Args:
            order_id: UUID primary key of the order.
            new_status: Target status string.
            _admin_user: The admin user making the change (reserved for future
                audit logging; currently unused).

        Returns:
            The updated ``Order`` instance.

        Raises:
            ValueError: If the order does not exist or ``new_status`` is
                not a recognised order status value.
        """
        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            raise ValueError("Order not found.")

        valid_statuses = [
            "placed",
            "confirmed",
            "preparing",
            "ready",
            "picked_up",
            "on_the_way",
            "delivered",
            "cancelled",
        ]
        if new_status not in valid_statuses:
            raise ValueError("Invalid status.")

        old_status = order.status
        order.status = new_status
        order.save(update_fields=["status", "updated_at"])
        OrderTracking.objects.create(
            order=order,
            status=new_status,
            description=f"Status updated by admin to {new_status}.",
        )

        order_status_updated.send(
            sender=Order,
            order=order,
            new_status=new_status,
            old_status=old_status,
        )

        # Logic for wallet balance updates upon delivery
        if new_status == "delivered" and old_status != "delivered":
            with transaction.atomic():
                # 1. Update Vendor Wallet: subtotal - coupon_discount
                # (Commission logic can be added here if there's a specific rate, 
                # using a flat calculation for now: earnings = subtotal - discount)
                vendor = order.vendor
                vendor_earnings = order.subtotal - order.coupon_discount
                vendor.wallet_balance += vendor_earnings
                vendor.save(update_fields=["wallet_balance", "updated_at"])

                # 2. Update Delivery Partner Wallet: delivery_fee
                if order.delivery_partner:
                    # We need to get the DeliveryPartner model instance, not just the User
                    from delivery.models import DeliveryPartner
                    try:
                        partner_profile = DeliveryPartner.objects.get(user=order.delivery_partner)
                        partner_profile.wallet_balance += order.delivery_fee
                        partner_profile.save(update_fields=["wallet_balance", "updated_at"])
                    except DeliveryPartner.DoesNotExist:
                        pass

        return order

    @staticmethod
    @transaction.atomic
    def add_issue_message(issue_id: str, user: User, message_text: str) -> dict:
        """Add a message to an order issue thread.

        Admin users can post on any issue; customers can only post on their
        own issues.  Posting a customer message on an ``open`` issue
        automatically transitions it to ``in_review``.

        Args:
            issue_id: UUID primary key of the ``OrderIssue``.
            user: The user posting the message.
            message_text: The message body.

        Returns:
            Serialised ``IssueMessage`` data dictionary.

        Raises:
            ValueError: If the issue is not found (or does not belong to the
                customer when ``user`` is not an admin).
        """
        is_admin = user.role == "admin"
        if is_admin:
            try:
                issue = OrderIssue.objects.get(id=issue_id)
            except OrderIssue.DoesNotExist:
                raise ValueError("Issue not found.")
        else:
            try:
                issue = OrderIssue.objects.get(id=issue_id, customer=user)
            except OrderIssue.DoesNotExist:
                raise ValueError("Issue not found.")

        issue_message = IssueMessage.objects.create(
            issue=issue,
            sender=user,
            is_admin=is_admin,
            message=message_text,
        )

        # Automatically progress issue state when the customer responds
        if issue.status == "open" and not is_admin:
            issue.status = "in_review"
            issue.save(update_fields=["status", "updated_at"])

        serializer = IssueMessageSerializer(issue_message)
        message_data = json.loads(
            JSONRenderer().render(serializer.data).decode("utf-8")
        )

        issue_message_added.send(
            sender=IssueMessage,
            issue_id=issue.id,
            message_data=message_data,
        )
        return serializer.data
