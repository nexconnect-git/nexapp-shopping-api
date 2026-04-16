import random
from django.utils import timezone
from vendors.actions.base import BaseAction
from orders.models import OrderTracking
from notifications.models import Notification
from delivery.models import DeliveryAssignment
from delivery.tasks import search_and_notify_partners


class UpdateOrderStatusAction(BaseAction):
    def execute(self, order, new_status: str, cancel_reason: str = None):
        cancel_reason = (cancel_reason or "").strip()
        allowed_transitions = {
            "placed": ["confirmed"],
            "confirmed": ["preparing"],
            "preparing": ["ready"],
        }
        current_allowed = allowed_transitions.get(order.status, [])
        if new_status not in current_allowed:
            raise ValueError(f"Cannot transition from '{order.status}' to '{new_status}'.")

        if new_status == "cancelled" and not cancel_reason:
            raise ValueError("A cancellation reason is required.")

        if new_status == "ready":
            order.delivery_otp = str(random.randint(100000, 999999))

        order.status = new_status
        order.save(update_fields=["status", "delivery_otp", "updated_at"])

        description_map = {
            "confirmed": "Order confirmed by vendor.",
            "preparing": "Order is being prepared.",
            "ready": "Order is ready for pickup by delivery partner.",
            "cancelled": f"Order cancelled by vendor. Reason: {cancel_reason}" if cancel_reason else "Order was cancelled by vendor.",
        }
        OrderTracking.objects.create(
            order=order,
            status=new_status,
            description=description_map.get(new_status, f"Order {new_status} by vendor."),
        )

        status_messages = {
            "confirmed": "Your order has been confirmed by the vendor.",
            "preparing": "Your order is being prepared.",
            "ready": "Your order is ready! A delivery partner will pick it up soon.",
            "cancelled": f"Your order #{order.order_number} was cancelled by the vendor. Reason: {cancel_reason}" if cancel_reason else f"Your order #{order.order_number} was cancelled by the vendor.",
        }
        Notification.objects.create(
            user=order.customer,
            title=f"Order {new_status.capitalize()}",
            message=status_messages.get(new_status, f"Your order status is now {new_status}."),
            notification_type="order",
            data={"order_id": str(order.id), "order_number": order.order_number},
        )

        # Auto-trigger delivery search when vendor marks order ready (if enabled for this vendor)
        if new_status == "ready" and order.vendor.auto_order_acceptance:
            try:
                StartDeliverySearchAction().execute(order)
            except ValueError:
                pass  # Already searching or partner assigned — safe to ignore

        return order


class VerifyPickupOtpAction(BaseAction):
    def execute(self, order, submitted_otp: str):
        if not order.delivery_partner:
            raise ValueError("No delivery partner assigned yet.")

        submitted_otp = str(submitted_otp or "").strip()
        if not submitted_otp:
            raise ValueError("OTP is required.")

        if order.pickup_otp != submitted_otp:
            raise ValueError("Invalid OTP. Please ask the delivery partner to check again.")

        order.status = "picked_up"
        order.save(update_fields=["status", "updated_at"])

        partner = order.delivery_partner.delivery_profile
        OrderTracking.objects.create(
            order=order,
            status="picked_up",
            description="Order picked up — pickup OTP verified by vendor.",
            latitude=partner.current_latitude,
            longitude=partner.current_longitude,
        )

        Notification.objects.create(
            user=order.customer,
            title="Order Picked Up",
            message=f"Your order #{order.order_number} has been picked up and is on its way!",
            notification_type="delivery",
            data={"order_id": str(order.id), "order_number": order.order_number},
        )
        return order


class StartDeliverySearchAction(BaseAction):
    """Vendor-initiated delivery partner search.

    Works for both the first search after marking an order ready and
    re-initiating after a timeout/cancel. Raises ValueError when a search
    is already active or a partner is already assigned.
    """

    def execute(self, order):
        if order.delivery_partner:
            raise ValueError("A delivery partner is already assigned.")

        assignment, created = DeliveryAssignment.objects.get_or_create(order=order)

        if not created and assignment.status in ("searching", "notified"):
            raise ValueError("A delivery partner search is already in progress.")

        if not created and assignment.status == "accepted":
            raise ValueError("A delivery partner is already assigned.")

        assignment.status = "searching"
        assignment.current_radius_km = 2.0
        assignment.last_search_at = timezone.now()
        assignment.save(update_fields=["status", "current_radius_km", "last_search_at", "updated_at"])
        assignment.notified_partners.clear()
        assignment.rejected_partners.clear()

        search_and_notify_partners.delay(str(assignment.id))

        return order


class CancelDeliverySearchAction(BaseAction):
    """Vendor cancels an in-progress delivery partner search.

    Clears pending partner notifications and marks the assignment cancelled
    so the 1-minute timeout job is a no-op when it eventually fires.
    """

    def execute(self, order):
        if order.delivery_partner:
            raise ValueError("A delivery partner is already assigned — cannot cancel search.")

        try:
            assignment = DeliveryAssignment.objects.get(order=order)
        except DeliveryAssignment.DoesNotExist:
            raise ValueError("No active search found for this order.")

        if assignment.status not in ("searching", "notified"):
            raise ValueError("No active search to cancel.")

        Notification.objects.filter(
            notification_type="delivery",
            data__assignment_id=str(assignment.id),
            data__type="assignment_request",
        ).delete()

        assignment.status = "cancelled"
        assignment.save(update_fields=["status", "updated_at"])
        assignment.notified_partners.clear()

        return order


# Backwards-compatible alias.
RetriggerPickupAction = StartDeliverySearchAction
