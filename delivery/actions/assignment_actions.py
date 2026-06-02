import secrets
from typing import Any
from django.db import transaction
from django.utils import timezone
from accounts.actions.audit_actions import CreateAdminAuditLogAction
from orders.models import Order, OrderTracking
from backend.events import order_status_updated
from delivery.data.assignment_repo import DeliveryAssignmentRepository
from orders.data.order_repo import OrderRepository
from delivery.tasks import search_and_notify_partners, _expand_and_retry
from notifications.fcm import send_push
from notifications.models import Notification
from helpers.geo_helpers import calculate_eta_minutes
from delivery.models import DeliveryAssignment, DeliveryPartner


class AcceptAssignmentAction:
    @staticmethod
    @transaction.atomic
    def execute(assignment_id: str, user: Any) -> Order:
        partner = user.delivery_profile
        try:
            assignment = (
                DeliveryAssignment.objects.select_for_update()
                .select_related("order")
                .get(pk=assignment_id)
            )
            if partner not in assignment.notified_partners.all() or assignment.status != "notified":
                raise ValueError("Request not found or no longer available.")
            order = (
                Order.objects.select_for_update()
                .select_related("customer", "vendor__user")
                .get(pk=assignment.order_id)
            )
        except Exception:
            raise ValueError("Request not found or no longer available.")

        if assignment.accepted_partner_id or order.delivery_partner_id is not None:
            raise ValueError("This order was already accepted by another partner.")

        assignment.order = order
        old_status = order.status
        order.delivery_partner = user
        order.pickup_otp = f"{secrets.randbelow(900000) + 100000}"

        # Calculate ETA if all coordinates are available
        save_fields = ["delivery_partner", "pickup_otp", "updated_at"]
        if (
            partner.current_latitude and partner.current_longitude
            and order.vendor.latitude and order.vendor.longitude
            and order.delivery_latitude and order.delivery_longitude
        ):
            order.estimated_delivery_time = calculate_eta_minutes(
                float(partner.current_latitude), float(partner.current_longitude),
                float(order.vendor.latitude), float(order.vendor.longitude),
                float(order.delivery_latitude), float(order.delivery_longitude),
            )
            save_fields.append("estimated_delivery_time")

        order.save(update_fields=save_fields)

        assignment.status = "accepted"
        assignment.accepted_partner = partner
        DeliveryAssignmentRepository.save(assignment, update_fields=["status", "accepted_partner", "updated_at"])

        # Delete any pending notifications so other partners' apps drop the request from their unread list
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
        # Notify customer and vendor that a driver accepted
        partner_name = user.get_full_name() or user.username
        driver_data = {"order_id": str(order.id), "order_number": order.order_number, "type": "driver_assigned"}
        for recipient, title, body in [
            (
                order.customer,
                "Driver Assigned",
                f"{partner_name} is heading to pick up your order #{order.order_number}.",
            ),
            (
                order.vendor.user,
                "Driver Accepted",
                f"{partner_name} accepted the delivery for order #{order.order_number}.",
            ),
        ]:
            Notification.objects.create(
                user=recipient,
                title=title,
                message=body,
                notification_type="delivery",
                data=driver_data,
            )
            try:
                send_push(recipient.pk, title=title, body=body, data=driver_data)
            except Exception:
                pass

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


class AdminReassignDeliveryAction:
    @staticmethod
    @transaction.atomic
    def execute(order_id: str, admin_user: Any, delivery_partner_id: str = "", reason: str = "", request=None) -> Order:
        try:
            order = (
                Order.objects.select_for_update()
                .select_related("customer", "vendor__user", "delivery_partner")
                .get(pk=order_id)
            )
        except Order.DoesNotExist:
            raise ValueError("Order not found.")

        if order.status in ["delivered", "cancelled"]:
            raise ValueError("Delivered or cancelled orders cannot be reassigned.")

        previous_partner_id = str(order.delivery_partner_id) if order.delivery_partner_id else ""
        old_status = order.status
        previous_partner = None
        if order.delivery_partner_id:
            try:
                previous_partner = order.delivery_partner.delivery_profile
            except Exception:
                previous_partner = None

        assignment, _ = DeliveryAssignmentRepository.get_or_create_for_order(order)
        assignment = (
            DeliveryAssignment.objects.select_for_update()
            .prefetch_related("notified_partners", "rejected_partners")
            .get(pk=assignment.pk)
        )

        reason_text = reason.strip() or "Manual admin dispatch reassignment."
        target_partner = None
        if delivery_partner_id:
            try:
                target_partner = DeliveryPartner.objects.select_for_update().select_related("user").get(
                    pk=delivery_partner_id,
                    is_approved=True,
                    status__in=["available", "on_delivery"],
                    user__is_active=True,
                )
            except Exception:
                raise ValueError("Delivery partner not found or unavailable.")

            order.delivery_partner = target_partner.user
            if not order.pickup_otp:
                order.pickup_otp = f"{secrets.randbelow(900000) + 100000}"
            order.save(update_fields=["delivery_partner", "pickup_otp", "updated_at"])

            assignment.status = "accepted"
            assignment.accepted_partner = target_partner
            assignment.last_search_at = timezone.now()
            DeliveryAssignmentRepository.save(
                assignment,
                update_fields=["status", "accepted_partner", "last_search_at", "updated_at"],
            )
            assignment.notified_partners.add(target_partner)
            assignment.rejected_partners.remove(target_partner)

            target_partner.status = "on_delivery"
            target_partner.save(update_fields=["status", "updated_at"])

            description = f"Admin reassigned delivery to {target_partner.user.get_full_name() or target_partner.user.username}. {reason_text}"
            event_status = "accepted"
        else:
            order.delivery_partner = None
            order.pickup_otp = ""
            if order.status not in ["placed", "confirmed", "preparing"]:
                order.status = "ready"
            order.save(update_fields=["delivery_partner", "pickup_otp", "status", "updated_at"])

            assignment.status = "searching"
            assignment.accepted_partner = None
            assignment.current_radius_km = 2.0
            assignment.last_search_at = timezone.now()
            DeliveryAssignmentRepository.save(
                assignment,
                update_fields=["status", "accepted_partner", "current_radius_km", "last_search_at", "updated_at"],
            )
            assignment.notified_partners.clear()
            assignment.rejected_partners.clear()
            search_and_notify_partners.delay(str(assignment.id))

            description = f"Admin cleared delivery partner and restarted dispatch search. {reason_text}"
            event_status = "searching"

        if previous_partner and previous_partner != target_partner:
            has_other_active_orders = Order.objects.filter(
                delivery_partner=previous_partner.user,
                status__in=["ready", "picked_up", "on_the_way"],
            ).exclude(pk=order.pk).exists()
            if has_other_active_orders:
                previous_partner.status = "on_delivery"
            else:
                previous_partner.status = "available"
            previous_partner.save(update_fields=["status", "updated_at"])

        OrderTracking.objects.create(
            order=order,
            status=order.status,
            description=description,
        )
        order_status_updated.send(sender=Order, order=order, new_status="delivery_reassigned", old_status=old_status)
        CreateAdminAuditLogAction().execute(
            request=request,
            actor=admin_user,
            action="status_change",
            entity_type="delivery_assignment",
            entity_id=str(assignment.id),
            summary=f"Reassigned delivery for order {order.order_number}",
            metadata={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "previous_partner_id": previous_partner_id,
                "new_partner_id": str(target_partner.id) if target_partner else "",
                "assignment_status": event_status,
                "reason": reason_text,
            },
        )
        Notification.objects.create(
            user=order.vendor.user,
            title="Dispatch Updated",
            message=f"Delivery dispatch was updated for order #{order.order_number}.",
            notification_type="delivery",
            data={"order_id": str(order.id), "assignment_id": str(assignment.id), "type": "dispatch_reassigned"},
        )
        Notification.objects.create(
            user=order.customer,
            title="Delivery Update",
            message=f"Delivery dispatch was updated for order #{order.order_number}.",
            notification_type="delivery",
            data={"order_id": str(order.id), "assignment_id": str(assignment.id), "type": "dispatch_reassigned"},
        )
        if target_partner:
            Notification.objects.create(
                user=target_partner.user,
                title="Delivery Assigned",
                message=f"You have been assigned order #{order.order_number}.",
                notification_type="delivery",
                data={"order_id": str(order.id), "assignment_id": str(assignment.id), "type": "manual_assignment"},
            )
        return order
