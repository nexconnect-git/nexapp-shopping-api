import random
from typing import Any
from django.db import transaction
from django.utils import timezone
from orders.models import Order, OrderTracking
from orders.data.order_repo import OrderRepository
from backend.events import order_status_updated
from delivery.data.earning_repo import DeliveryEarningRepository


class AcceptDeliveryAction:
    @staticmethod
    @transaction.atomic
    def execute(order_id: str, user: Any) -> Order:
        try:
            order = OrderRepository.get_by_id(order_id)
            if order.status != "ready" or order.delivery_partner is not None:
                raise ValueError("Order not found or already assigned.")
        except Exception:
            raise ValueError("Order not found or already assigned.")

        partner = user.delivery_profile
        order.delivery_partner = user
        order.save(update_fields=["delivery_partner", "updated_at"])

        partner.status = "on_delivery"
        partner.save(update_fields=["status", "updated_at"])

        OrderTracking.objects.create(
            order=order,
            status="ready",
            description=f"Delivery partner {user.get_full_name() or user.username} accepted the order.",
            latitude=partner.current_latitude,
            longitude=partner.current_longitude,
        )
        order_status_updated.send(sender=Order, order=order, new_status="ready", old_status="ready")
        return order


class UpdateDeliveryStatusAction:
    @staticmethod
    @transaction.atomic
    def execute(order_id: str, new_status: str, user: Any) -> Order:
        try:
            order = OrderRepository.get_by_id(order_id)
            if order.delivery_partner != user or order.status != "picked_up":
                raise ValueError("Order not found or not in 'picked_up' status.")
        except Exception:
            raise ValueError("Order not found or not in 'picked_up' status.")

        allowed_statuses = ["on_the_way"]
        if new_status not in allowed_statuses:
            raise ValueError(f"Status must be one of: {', '.join(allowed_statuses)}.")

        old_status = order.status
        order.status = new_status

        update_fields = ["status", "updated_at"]
        if new_status == "on_the_way" and not order.delivery_otp:
            order.delivery_otp = str(random.randint(100000, 999999))
            update_fields.append("delivery_otp")

        order.save(update_fields=update_fields)

        partner = user.delivery_profile
        description_map = {
            "picked_up": "Order picked up from vendor.",
            "on_the_way": "Order is on the way.",
        }

        OrderTracking.objects.create(
            order=order,
            status=new_status,
            description=description_map.get(new_status, ""),
            latitude=partner.current_latitude,
            longitude=partner.current_longitude,
        )
        order_status_updated.send(sender=Order, order=order, new_status=new_status, old_status=old_status)
        return order


class ConfirmDeliveryAction:
    @staticmethod
    @transaction.atomic
    def execute(order_id: str, user: Any, submitted_otp: str, photo: Any, transaction_photo: Any = None) -> Order:
        try:
            order = OrderRepository.get_by_id(order_id)
            if order.delivery_partner != user or order.status != "on_the_way":
                raise ValueError("Order not found or not in 'on_the_way' status.")
        except Exception:
            raise ValueError("Order not found or not in 'on_the_way' status.")

        if not submitted_otp:
            raise ValueError("OTP is required.")

        if order.delivery_otp and order.delivery_otp != submitted_otp:
            raise ValueError("Invalid OTP. Please check with the customer.")

        if not photo:
            raise ValueError("A delivery photo is required.")

        old_status = order.status
        order.status = "delivered"
        order.actual_delivery_time = timezone.now()
        order.delivery_photo = photo
        
        update_fields = ["status", "actual_delivery_time", "delivery_photo", "updated_at"]
        if transaction_photo:
            order.transaction_photo = transaction_photo
            update_fields.append("transaction_photo")

        order.save(update_fields=update_fields)

        partner = user.delivery_profile
        base_qs = OrderRepository.get_base_queryset()
        has_active_orders = base_qs.filter(
            delivery_partner=user, status__in=["ready", "picked_up", "on_the_way"]
        ).exists()

        partner.status = "on_delivery" if has_active_orders else "available"
        partner.total_deliveries += 1
        DeliveryEarningRepository.create(partner=partner, order=order, amount=order.delivery_fee)
        partner.total_earnings += order.delivery_fee
        partner.save(update_fields=["status", "total_deliveries", "total_earnings", "updated_at"])

        OrderTracking.objects.create(
            order=order,
            status="delivered",
            description="Order delivered and confirmed with OTP.",
            latitude=partner.current_latitude,
            longitude=partner.current_longitude,
        )
        order_status_updated.send(sender=Order, order=order, new_status="delivered", old_status=old_status)
        return order
