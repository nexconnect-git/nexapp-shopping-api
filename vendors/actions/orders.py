from django.db import transaction
from django.utils import timezone
from vendors.actions.base import BaseAction
from orders.actions import OrderCancellationEffectsAction
from orders.data.order_repo import OrderRepository
from notifications.data.notification_repository import NotificationRepository
from delivery.models import DeliveryAssignment
from delivery.data.assignment_repo import DeliveryAssignmentRepository
from delivery.tasks import search_and_notify_partners
from backend.events import order_cancelled
from vendors.realtime import broadcast_order_event


class UpdateOrderStatusAction(BaseAction):
    @transaction.atomic
    def execute(self, order, new_status: str, cancel_reason: str = None, expected_status=None):
        order = OrderRepository.get_locked(order.pk)
        if expected_status and order.status != expected_status:
            raise ValueError(f"Order is now '{order.status}'. Refresh before trying again.")
        cancel_reason = (cancel_reason or "").strip()
        # Vendors may cancel any order that hasn't been picked up yet
        vendor_cancel_allowed = ["placed", "confirmed", "preparing", "ready"]
        if new_status == "cancelled":
            if order.status not in vendor_cancel_allowed:
                raise ValueError(
                    "Cannot cancel an order that has already been dispatched or delivered."
                )
            if not cancel_reason:
                raise ValueError("A cancellation reason is required.")
        else:
            allowed_transitions = {
                "placed": ["confirmed"],
                "confirmed": ["preparing"],
                "preparing": ["ready"],
            }
            current_allowed = allowed_transitions.get(order.status, [])
            if new_status not in current_allowed:
                raise ValueError(f"Cannot transition from '{order.status}' to '{new_status}'.")

        old_status = order.status
        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

        description_map = {
            "confirmed": "Order confirmed by vendor.",
            "preparing": "Order is being prepared.",
            "ready": "Order is ready for pickup by delivery partner.",
            "cancelled": f"Order cancelled by vendor. Reason: {cancel_reason}" if cancel_reason else "Order was cancelled by vendor.",
        }
        OrderRepository.add_tracking(
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
        NotificationRepository().create(
            user=order.customer,
            title=f"Order {new_status.capitalize()}",
            message=status_messages.get(new_status, f"Your order status is now {new_status}."),
            notification_type="order",
            data={"order_id": str(order.id), "order_number": order.order_number},
        )
        transaction.on_commit(lambda: broadcast_order_event(order, "order_updated"))


        if new_status == "cancelled":
            OrderCancellationEffectsAction().execute(order)

            order_cancelled.send(sender=order.__class__, order=order)

        return order


class VerifyPickupOtpAction(BaseAction):
    @transaction.atomic
    def execute(self, order, submitted_otp: str):
        order = OrderRepository.get_locked(order.pk)
        if order.status != 'ready':
            raise ValueError('Only ready orders can be picked up.')
        if not order.delivery_partner:
            raise ValueError("No delivery partner assigned yet.")

        submitted_otp = str(submitted_otp or "").strip()
        if len(submitted_otp) != 6 or not submitted_otp.isascii() or not submitted_otp.isdigit():
            raise ValueError("Enter the six-digit pickup OTP.")

        if order.pickup_otp != submitted_otp:
            raise ValueError("Invalid OTP. Please ask the delivery partner to check again.")

        order.status = "picked_up"
        order.save(update_fields=["status", "updated_at"])

        partner = order.delivery_partner.delivery_profile
        OrderRepository.add_tracking(
            order=order,
            status="picked_up",
            description="Order picked up — pickup OTP verified by vendor.",
            latitude=partner.current_latitude,
            longitude=partner.current_longitude,
        )

        NotificationRepository().create(
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

    @transaction.atomic
    def execute(self, order):
        order = OrderRepository.get_locked(order.pk)
        if order.status != 'ready':
            raise ValueError('Only ready orders can start delivery search.')
        if order.delivery_partner:
            raise ValueError("A delivery partner is already assigned.")

        assignment, created = DeliveryAssignmentRepository.get_or_create_for_order(order)
        assignment = DeliveryAssignmentRepository.get_locked(assignment.pk)

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

        def enqueue_search():
            try:
                search_and_notify_partners.delay(str(assignment.id))
            except Exception as error:
                with transaction.atomic():
                    current = DeliveryAssignmentRepository.get_locked(assignment.pk)
                    if current.status == 'searching' and current.last_search_at == assignment.last_search_at:
                        current.status = 'failed'
                        DeliveryAssignmentRepository.save(current, update_fields=['status', 'updated_at'])
                broadcast_order_event(order)
                raise ValueError('Driver search could not be queued. Retry when dispatch is available.') from error
            broadcast_order_event(order)
        transaction.on_commit(enqueue_search)

        return order


class CancelDeliverySearchAction(BaseAction):
    """Vendor cancels an in-progress delivery partner search.

    Clears pending partner notifications and marks the assignment cancelled
    so the 1-minute timeout job is a no-op when it eventually fires.
    """

    @transaction.atomic
    def execute(self, order):
        order = OrderRepository.get_locked(order.pk)
        if order.delivery_partner:
            raise ValueError("A delivery partner is already assigned — cannot cancel search.")

        assignment = DeliveryAssignmentRepository.get_locked_for_order(order)
        if not assignment:
            raise ValueError("No active search found for this order.")

        if assignment.status not in ("searching", "notified"):
            raise ValueError("No active search to cancel.")

        NotificationRepository().filter(
            notification_type="delivery",
            data__assignment_id=str(assignment.id),
            data__type="assignment_request",
        ).delete()

        assignment.status = "cancelled"
        assignment.save(update_fields=["status", "updated_at"])
        assignment.notified_partners.clear()
        transaction.on_commit(lambda: broadcast_order_event(order))

        return order


class AcceptOrderAction(BaseAction):
    def execute(self, order):
        if order.status != "placed":
            raise ValueError("Only new orders can be accepted.")
        return UpdateOrderStatusAction().execute(order, "confirmed", expected_status='placed')


class RejectOrderAction(BaseAction):
    def execute(self, order, reason: str):
        reason = (reason or "").strip() or "Rejected by vendor."
        if order.status != "placed":
            raise ValueError("Only new orders can be rejected.")
        return UpdateOrderStatusAction().execute(order, "cancelled", reason, expected_status='placed')


class StartPreparingOrderAction(BaseAction):
    def execute(self, order):
        if order.status != "confirmed":
            raise ValueError("Only confirmed orders can move to preparing.")
        return UpdateOrderStatusAction().execute(order, "preparing", expected_status='confirmed')


class MarkOrderReadyAction(BaseAction):
    def execute(self, order):
        if order.status != "preparing":
            raise ValueError("Only preparing orders can be marked ready.")
        return UpdateOrderStatusAction().execute(order, "ready", expected_status='preparing')


# Backwards-compatible alias.
RetriggerPickupAction = StartDeliverySearchAction
