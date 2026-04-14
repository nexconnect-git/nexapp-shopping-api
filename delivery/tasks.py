"""
Background tasks for the ``delivery`` app.

These tasks are processed by RQ workers.
"""

import logging
import time
from datetime import timedelta

import django_rq
from django_rq import job
from django.utils import timezone

from backend.utils import haversine
from delivery.models import DeliveryAssignment, DeliveryPartner
from notifications.models import Notification

logger = logging.getLogger(__name__)


@job("default", timeout=90)
def delayed_timeout_check(assignment_id: str) -> None:
    """Sleep 60 s then call check_assignment_timeout — reliable fallback scheduler.

    Enqueued immediately as a regular RQ job (no rq-scheduler dependency).
    The 60-second sleep inside the worker ensures the timeout fires even when
    the rq-scheduler service is not polling fast enough or enqueue_in is
    unavailable.

    Args:
        assignment_id: UUID string primary key of the ``DeliveryAssignment``.
    """
    time.sleep(60)
    check_assignment_timeout(assignment_id)


@job("default")
def search_and_notify_partners(assignment_id: str) -> None:
    """Find available delivery partners within the assignment's search radius and notify them.

    Queries approved, available partners with a known location and calculates
    their distance from the vendor. Partners within ``assignment.current_radius_km``
    are notified via in-app notification and added to the assignment's
    ``notified_partners`` set.

    If no candidates are found the search radius is expanded via
    ``_expand_and_retry``. A 1-minute timeout check is also scheduled so that
    the vendor is alerted when no partner accepts.

    Note:
        Model imports are inline to prevent circular import errors in RQ workers.

    Args:
        assignment_id: UUID string primary key of the ``DeliveryAssignment``.
    """
    try:
        assignment = (
            DeliveryAssignment.objects
            .select_related("order__vendor")
            .prefetch_related("notified_partners", "rejected_partners")
            .get(id=assignment_id)
        )
    except DeliveryAssignment.DoesNotExist:
        return

    if assignment.status in ("accepted", "cancelled", "timed_out"):
        return

    # Skip if the assignment was stuck in the queue for more than 1 minute
    if timezone.now() - assignment.last_search_at > timedelta(minutes=1):
        if assignment.status != "timed_out":
            check_assignment_timeout(str(assignment.id))
        return

    order = assignment.order
    vendor_lat = float(order.vendor.latitude)
    vendor_lng = float(order.vendor.longitude)

    already_notified_ids = set(
        assignment.notified_partners.values_list("id", flat=True)
    )

    # Partners with an active accepted assignment are considered busy
    busy_partner_ids = set(
        DeliveryAssignment.objects.filter(
            status="accepted",
            accepted_partner__isnull=False,
            order__status__in=["ready", "picked_up", "on_the_way"],
        ).values_list("accepted_partner_id", flat=True)
    )

    candidates = DeliveryPartner.objects.filter(
        is_approved=True,
        status="available",
        current_latitude__isnull=False,
        current_longitude__isnull=False,
    ).exclude(id__in=already_notified_ids).exclude(id__in=busy_partner_ids)

    nearby_partners = [
        partner for partner in candidates
        if haversine(
            float(partner.current_latitude),
            float(partner.current_longitude),
            vendor_lat,
            vendor_lng,
        ) <= assignment.current_radius_km
    ]

    if nearby_partners:
        for partner in nearby_partners:
            assignment.notified_partners.add(partner)
            Notification.objects.create(
                user=partner.user,
                title="New Delivery Request",
                message=(
                    f"Order #{order.order_number} needs pickup near you "
                    f"(within {assignment.current_radius_km:.0f} km)."
                ),
                notification_type="delivery",
                data={
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                    "assignment_id": str(assignment.id),
                    "type": "assignment_request",
                },
            )
        assignment.status = "notified"
        assignment.last_search_at = timezone.now()
        assignment.save(update_fields=["status", "last_search_at", "updated_at"])
        logger.info(
            "Assignment %s: notified %d partners within %s km",
            assignment_id,
            len(nearby_partners),
            assignment.current_radius_km,
        )
        # Schedule a 1-minute timeout — if no one accepts, notify the vendor to retrigger.
        # Strategy: try rq-scheduler first (most accurate), fall back to a plain
        # delayed_timeout_check job that sleeps 60 s inside the worker process.
        scheduled = False
        try:
            scheduler = django_rq.get_scheduler("default")
            scheduler.enqueue_in(
                timedelta(minutes=1),
                check_assignment_timeout,
                str(assignment_id),
            )
            scheduled = True
            logger.info("Assignment %s: timeout scheduled via rq-scheduler", assignment_id)
        except Exception:
            logger.warning(
                "Assignment %s: rq-scheduler unavailable, using delayed_timeout_check fallback",
                assignment_id,
            )
        if not scheduled:
            delayed_timeout_check.delay(str(assignment_id))
    else:
        _expand_and_retry(assignment)


def _expand_and_retry(assignment) -> None:
    """Expand the search radius and re-queue a partner search.

    Increases ``current_radius_km`` by 2 km. When the maximum radius is
    exceeded, the radius cycles back to 2 km and the notified-partners list is
    cleared so all partners can receive the request again.

    A 2-second sleep is inserted to prevent tight infinite loops in background
    workers.

    Args:
        assignment: The ``DeliveryAssignment`` instance to retry.
    """
    assignment.current_radius_km += 2.0
    if assignment.current_radius_km > assignment.max_radius_km:
        # Cycle back and allow all partners to be notified again
        assignment.current_radius_km = 2.0
        assignment.notified_partners.clear()
        logger.info(
            "Assignment %s: cycled back to 2 km, cleared notified partners",
            assignment.id,
        )

    # Small delay to prevent tight infinite looping in background workers
    time.sleep(2)

    # Re-fetch so we don't overwrite a cancel/accept that arrived during the sleep.
    assignment.refresh_from_db()
    if assignment.status in ("accepted", "cancelled", "timed_out", "failed"):
        logger.info(
            "Assignment %s: aborting expand/retry — status is now '%s'",
            assignment.id,
            assignment.status,
        )
        return

    assignment.status = "searching"
    assignment.last_search_at = timezone.now()
    assignment.save(update_fields=["status", "current_radius_km", "last_search_at", "updated_at"])
    search_and_notify_partners.delay(str(assignment.id))
    logger.info(
        "Assignment %s: expanding/cycling to %s km",
        assignment.id,
        assignment.current_radius_km,
    )


@job("default")
def check_assignment_timeout(assignment_id: str) -> None:
    """Handle a 1-minute partner-notification timeout.

    Runs 1 minute after partners are notified. If nobody has accepted yet,
    clears pending partner notifications, marks the assignment as
    ``timed_out``, and sends a notification to the vendor so they can
    retrigger the pickup-ready status.

    Note:
        Model imports are inline to prevent circular import errors in RQ workers.

    Args:
        assignment_id: UUID string primary key of the ``DeliveryAssignment``.
    """
    try:
        assignment = DeliveryAssignment.objects.select_related(
            "order__vendor__user"
        ).get(id=assignment_id)
    except DeliveryAssignment.DoesNotExist:
        return

    if assignment.status not in ("notified", "searching"):
        return

    # Skip if the assignment was recently retriggered or expanded (obsolete timeout)
    if timezone.now() - assignment.last_search_at < timedelta(seconds=55):
        return

    order = assignment.order

    # Remove pending partner notifications so they no longer see the request
    deleted_count, _ = Notification.objects.filter(
        notification_type="delivery",
        data__assignment_id=str(assignment_id),
        data__type="assignment_request",
    ).delete()
    logger.info(
        "Assignment %s: deleted %d partner notification(s)",
        assignment_id,
        deleted_count,
    )

    assignment.status = "timed_out"
    assignment.save(update_fields=["status", "updated_at"])
    logger.info("Assignment %s: timed out — notifying vendor", assignment_id)

    Notification.objects.create(
        user=order.vendor.user,
        title="No Delivery Partner Found",
        message=(
            "No delivery partner found or all delivery partners in this area are busy. "
            "Please reinitiate the delivery status."
        ),
        notification_type="delivery",
        data={
            "order_id": str(order.id),
            "order_number": order.order_number,
            "type": "assignment_timeout",
        },
    )


def check_stale_assignments() -> None:
    """Process stale delivery assignments on partner polling and location updates.

    Handles two cases:
      - ``notified`` assignments idle for > 1 minute: timeout and notify vendor.
      - ``searching`` assignments idle for > 2 minutes: re-fire search in case
        new partners have come online since the last attempt.

    """
    timeout_threshold = timezone.now() - timedelta(minutes=1)
    stale_threshold = timezone.now() - timedelta(minutes=2)

    # Expire notified assignments that nobody accepted within 1 minute
    timed_out_assignments = DeliveryAssignment.objects.filter(
        status="notified",
        last_search_at__lt=timeout_threshold,
    )
    for assignment in timed_out_assignments:
        logger.info("Assignment %s: 1-min timeout reached, expiring", assignment.id)
        check_assignment_timeout(str(assignment.id))

    # Re-trigger searches for assignments stuck in 'searching'
    stale_searching = DeliveryAssignment.objects.filter(
        status="searching",
        last_search_at__lt=stale_threshold,
    )
    for assignment in stale_searching:
        logger.info(
            "Assignment %s: retrying search for newly online partners",
            assignment.id,
        )
        assignment.last_search_at = timezone.now()
        assignment.save(update_fields=["last_search_at", "updated_at"])
        search_and_notify_partners.delay(str(assignment.id))
