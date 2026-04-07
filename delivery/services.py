"""Service layer for the delivery app.

Manages the delivery lifecycle: accepting orders, updating transit status,
confirming delivery (OTP + photo), and handling assignment accept/cancel flows.
"""

import random
from typing import Any

from django.db import transaction
from django.utils import timezone

from delivery.models import (
    DeliveryAssignment,
    DeliveryEarning,
)
from delivery.tasks import search_and_notify_partners
from orders.models import Order, OrderTracking
from backend.events import order_status_updated


class DeliveryService:
    """Stateless service class for delivery-related business operations."""

    @staticmethod
    @transaction.atomic
    def accept_delivery(order_id: str, user: Any) -> Order:
        """Assign a delivery partner to a ready, unassigned order.

        Sets the order's ``delivery_partner``, changes the partner status to
        ``on_delivery``, creates a tracking entry, and fires the
        ``order_status_updated`` signal.

        Args:
            order_id: UUID primary key of the order (must be ``ready``
                with no partner assigned).
            user: The authenticated delivery-partner user.

        Returns:
            The updated ``Order`` instance.

        Raises:
            ValueError: If the order is not found or is already assigned.
        """
        try:
            order = Order.objects.get(
                pk=order_id, status="ready", delivery_partner__isnull=True
            )
        except Order.DoesNotExist:
            raise ValueError("Order not found or already assigned.")

        partner = user.delivery_profile
        order.delivery_partner = user
        order.save(update_fields=["delivery_partner", "updated_at"])

        partner.status = "on_delivery"
        partner.save(update_fields=["status", "updated_at"])

        OrderTracking.objects.create(
            order=order,
            status="ready",
            description=(
                f"Delivery partner "
                f"{user.get_full_name() or user.username} accepted the order."
            ),
            latitude=partner.current_latitude,
            longitude=partner.current_longitude,
        )
        order_status_updated.send(
            sender=Order,
            order=order,
            new_status="ready",
            old_status="ready",
        )
        return order

    @staticmethod
    @transaction.atomic
    def update_delivery_status(
        order_id: str, new_status: str, user: Any
    ) -> Order:
        """Transition a picked-up order to ``on_the_way``.

        Args:
            order_id: UUID primary key of the order.
            new_status: Target status; currently only ``"on_the_way"`` is
                permitted from a ``picked_up`` order.
            user: The authenticated delivery-partner user.

        Returns:
            The updated ``Order`` instance.

        Raises:
            ValueError: If the order is not found/not in ``picked_up`` status,
                or ``new_status`` is not an allowed transition.
        """
        try:
            order = Order.objects.get(
                pk=order_id, delivery_partner=user, status="picked_up"
            )
        except Order.DoesNotExist:
            raise ValueError(
                "Order not found or not in 'picked_up' status."
            )

        allowed_statuses = ["on_the_way"]
        if new_status not in allowed_statuses:
            raise ValueError(
                f"Status must be one of: {', '.join(allowed_statuses)}."
            )

        old_status = order.status
        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

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
        order_status_updated.send(
            sender=Order,
            order=order,
            new_status=new_status,
            old_status=old_status,
        )
        return order

    @staticmethod
    @transaction.atomic
    def confirm_delivery(
        order_id: str, user: Any, submitted_otp: str, photo: Any
    ) -> Order:
        """Mark an order as delivered after OTP verification and photo upload.

        Updates the order, increments the partner's delivery counter and
        earnings, and records delivery earnings.

        Args:
            order_id: UUID primary key of the order (must be ``on_the_way``).
            user: The authenticated delivery-partner user.
            submitted_otp: OTP string provided by the customer.
            photo: Uploaded delivery-confirmation photo file.

        Returns:
            The updated ``Order`` instance.

        Raises:
            ValueError: If the order is not found, OTP is missing/invalid,
                or the photo is not provided.
        """
        try:
            order = Order.objects.get(
                pk=order_id, delivery_partner=user, status="on_the_way"
            )
        except Order.DoesNotExist:
            raise ValueError(
                "Order not found or not in 'on_the_way' status."
            )

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
        order.save(
            update_fields=[
                "status",
                "actual_delivery_time",
                "delivery_photo",
                "updated_at",
            ]
        )

        partner = user.delivery_profile
        # Check whether the partner has more active orders before going idle
        has_active_orders = Order.objects.filter(
            delivery_partner=user, status__in=["ready", "picked_up", "on_the_way"]
        ).exists()

        partner.status = "on_delivery" if has_active_orders else "available"
        partner.total_deliveries += 1
        DeliveryEarning.objects.create(
            delivery_partner=partner, order=order, amount=order.delivery_fee
        )
        partner.total_earnings += order.delivery_fee
        partner.save(
            update_fields=[
                "status",
                "total_deliveries",
                "total_earnings",
                "updated_at",
            ]
        )

        OrderTracking.objects.create(
            order=order,
            status="delivered",
            description="Order delivered and confirmed with OTP.",
            latitude=partner.current_latitude,
            longitude=partner.current_longitude,
        )
        order_status_updated.send(
            sender=Order,
            order=order,
            new_status="delivered",
            old_status=old_status,
        )
        return order

    @staticmethod
    @transaction.atomic
    def accept_assignment(assignment_id: str, user: Any) -> Order:
        """Accept a delivery assignment that was sent to this partner.

        Generates a pickup OTP for the vendor verification step, marks the
        assignment as ``accepted``, and transitions the partner to
        ``on_delivery``.

        Args:
            assignment_id: UUID primary key of the ``DeliveryAssignment``.
            user: The authenticated delivery-partner user.

        Returns:
            The associated ``Order`` instance.

        Raises:
            ValueError: If the assignment is not found, the partner was not
                notified for it, or the order is already taken.
        """
        partner = user.delivery_profile
        try:
            assignment = DeliveryAssignment.objects.select_related(
                "order"
            ).get(
                id=assignment_id,
                notified_partners=partner,
                status="notified",
            )
        except DeliveryAssignment.DoesNotExist:
            raise ValueError("Request not found or no longer available.")

        if assignment.order.delivery_partner is not None:
            raise ValueError(
                "This order was already accepted by another partner."
            )

        order = assignment.order
        old_status = order.status
        order.delivery_partner = user
        order.pickup_otp = str(random.randint(100000, 999999))
        order.save(
            update_fields=["delivery_partner", "pickup_otp", "updated_at"]
        )

        assignment.status = "accepted"
        assignment.accepted_partner = partner
        assignment.save(
            update_fields=["status", "accepted_partner", "updated_at"]
        )

        partner.status = "on_delivery"
        partner.save(update_fields=["status", "updated_at"])

        OrderTracking.objects.create(
            order=order,
            status="ready",
            description=(
                f"Delivery partner "
                f"{user.get_full_name() or user.username} accepted the order."
            ),
            latitude=partner.current_latitude,
            longitude=partner.current_longitude,
        )
        order_status_updated.send(
            sender=Order,
            order=order,
            new_status="ready",
            old_status=old_status,
        )
        return order

    @staticmethod
    @transaction.atomic
    def cancel_assignment(order_id: str, user: Any) -> Order:
        """Cancel an accepted delivery assignment and restart the partner search.

        Resets the order's partner assignment, creates a new
        ``DeliveryAssignment``, and asynchronously re-searches for a partner.

        Args:
            order_id: UUID primary key of the order.
            user: The delivery-partner user cancelling the assignment.

        Returns:
            The updated ``Order`` instance (back to ``ready`` with no partner).

        Raises:
            ValueError: If the order is not found.
        """
        try:
            order = Order.objects.get(
                pk=order_id,
                delivery_partner=user,
                status__in=["ready", "picked_up"],
            )
        except Order.DoesNotExist:
            raise ValueError("Order not found.")

        partner = user.delivery_profile
        old_status = order.status

        order.delivery_partner = None
        order.pickup_otp = ""
        order.status = "ready"
        order.save(
            update_fields=[
                "delivery_partner",
                "pickup_otp",
                "status",
                "updated_at",
            ]
        )

        partner.status = "available"
        partner.save(update_fields=["status", "updated_at"])

        OrderTracking.objects.create(
            order=order,
            status="ready",
            description=(
                "Delivery partner cancelled. Re-searching for a new partner."
            ),
        )

        order_status_updated.send(
            sender=Order,
            order=order,
            new_status="reassigned",
            old_status=old_status,
        )

        # Reset the assignment record and kick off a fresh partner search
        assignment, _ = DeliveryAssignment.objects.get_or_create(order=order)
        assignment.status = "searching"
        assignment.accepted_partner = None
        assignment.current_radius_km = 2.0
        assignment.last_search_at = timezone.now()
        assignment.save(
            update_fields=["status", "accepted_partner", "current_radius_km", "last_search_at", "updated_at"]
        )
        assignment.notified_partners.clear()
        assignment.rejected_partners.clear()

        search_and_notify_partners.delay(str(assignment.id))

        return order
