import random
from typing import Any
from django.db import transaction
from django.utils import timezone
from orders.models import Order, OrderTracking
from backend.events import order_status_updated
from delivery.data.assignment_repo import DeliveryAssignmentRepository
from orders.data.order_repo import OrderRepository
from delivery.tasks import search_and_notify_partners, _expand_and_retry


class AcceptAssignmentAction:
    @staticmethod
    @transaction.atomic
    def execute(assignment_id: str, user: Any) -> Order:
        partner = user.delivery_profile
        try:
            assignment = DeliveryAssignmentRepository.get_by_id(
                pk=assignment_id,
                select_related=["order"]
            )
            if partner not in assignment.notified_partners.all() or assignment.status != "notified":
                raise ValueError("Request not found or no longer available.")
        except Exception:
            raise ValueError("Request not found or no longer available.")

        if assignment.order.delivery_partner is not None:
            raise ValueError("This order was already accepted by another partner.")

        order = assignment.order
        old_status = order.status
        order.delivery_partner = user
        order.pickup_otp = str(random.randint(100000, 999999))
        order.save(update_fields=["delivery_partner", "pickup_otp", "updated_at"])

        assignment.status = "accepted"
        assignment.accepted_partner = partner
        DeliveryAssignmentRepository.save(assignment, update_fields=["status", "accepted_partner", "updated_at"])

        # Delete any pending notifications so other partners' apps drop the request from their unread list
        from notifications.models import Notification
        Notification.objects.filter(
            notification_type="delivery",
            data__assignment_id=str(assignment_id),
            data__type="assignment_request",
        ).delete()

        partner.status = "on_delivery"
        partner.save(update_fields=["status", "updated_at"])

        OrderTracking.objects.create(
            order=order,
            status=old_status,
            description=f"Delivery partner {user.get_full_name() or user.username} accepted the assignment.",
            latitude=partner.current_latitude,
            longitude=partner.current_longitude,
        )
        # We only fire order_status_updated if we actually change the status, which we do not here.
        return order


class RejectAssignmentAction:
    @staticmethod
    @transaction.atomic
    def execute(assignment_id: str, user: Any) -> bool:
        partner = user.delivery_profile
        try:
            assignment = DeliveryAssignmentRepository.get_by_id(
                pk=assignment_id,
                prefetch=["notified_partners", "rejected_partners"]
            )
            if partner not in assignment.notified_partners.all():
                raise ValueError("Request not found.")
        except Exception:
            raise ValueError("Request not found.")

        if assignment.status in ("accepted", "cancelled", "failed"):
            return False

        assignment.rejected_partners.add(partner)

        if assignment.rejected_partners.count() >= assignment.notified_partners.count():
            _expand_and_retry(assignment)

        return True


class CancelAssignmentAction:
    @staticmethod
    @transaction.atomic
    def execute(order_id: str, user: Any) -> Order:
        try:
            order = OrderRepository.get_by_id(order_id)
            if order.delivery_partner != user or order.status not in ["ready", "picked_up"]:
                raise ValueError("Order not found.")
        except Exception:
            raise ValueError("Order not found.")

        partner = user.delivery_profile
        old_status = order.status

        order.delivery_partner = None
        order.pickup_otp = ""
        order.status = "ready"
        order.save(update_fields=["delivery_partner", "pickup_otp", "status", "updated_at"])

        partner.status = "available"
        partner.save(update_fields=["status", "updated_at"])

        OrderTracking.objects.create(
            order=order,
            status="ready",
            description="Delivery partner cancelled. Re-searching for a new partner.",
        )

        order_status_updated.send(sender=Order, order=order, new_status="reassigned", old_status=old_status)

        assignment, _ = DeliveryAssignmentRepository.get_or_create_for_order(order)
        assignment.status = "searching"
        assignment.accepted_partner = None
        assignment.current_radius_km = 2.0
        assignment.last_search_at = timezone.now()
        DeliveryAssignmentRepository.save(
            assignment, 
            update_fields=["status", "accepted_partner", "current_radius_km", "last_search_at", "updated_at"]
        )
        assignment.notified_partners.clear()
        assignment.rejected_partners.clear()

        search_and_notify_partners.delay(str(assignment.id))

        return order
