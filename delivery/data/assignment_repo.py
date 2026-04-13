from django.db.models import QuerySet
from django.utils import timezone
from datetime import timedelta
from delivery.models import DeliveryAssignment


class DeliveryAssignmentRepository:
    """Repository for DeliveryAssignment database operations."""

    @staticmethod
    def get_by_id(pk: str, prefetch: list = None, select_related: list = None) -> DeliveryAssignment:
        qs = DeliveryAssignment.objects.all()
        if select_related:
            qs = qs.select_related(*select_related)
        if prefetch:
            qs = qs.prefetch_related(*prefetch)
        return qs.get(pk=pk)

    @staticmethod
    def get_pending_for_partner(partner, exclude_rejected: bool = True, prefetch: list = None, select_related: list = None) -> QuerySet[DeliveryAssignment]:
        qs = DeliveryAssignment.objects.filter(
            notified_partners=partner,
            status="notified",
        )
        if exclude_rejected:
            qs = qs.exclude(rejected_partners=partner)
        if select_related:
            qs = qs.select_related(*select_related)
        if prefetch:
            qs = qs.prefetch_related(*prefetch)
        return qs

    @staticmethod
    def get_expired_for_partner(partner, minutes_old: int = 1) -> QuerySet[DeliveryAssignment]:
        cutoff = timezone.now() - timedelta(minutes=minutes_old)
        return DeliveryAssignment.objects.filter(
            notified_partners=partner,
            status="notified",
            last_search_at__lt=cutoff,
        )

    @staticmethod
    def get_active_assignments() -> QuerySet[DeliveryAssignment]:
        return DeliveryAssignment.objects.filter(
            status__in=["searching", "notified"]
        )

    @staticmethod
    def get_or_create_for_order(order) -> tuple[DeliveryAssignment, bool]:
        return DeliveryAssignment.objects.get_or_create(order=order)

    @staticmethod
    def save(instance: DeliveryAssignment, update_fields: list = None) -> DeliveryAssignment:
        instance.save(update_fields=update_fields)
        return instance
