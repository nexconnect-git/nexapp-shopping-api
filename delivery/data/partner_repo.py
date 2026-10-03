from django.db.models import QuerySet
from django.utils import timezone
from delivery.models import DeliveryPartner
from vendors.data.base import BaseRepository


class DeliveryPartnerRepository(BaseRepository):
    """Repository for DeliveryPartner database operations."""

    def __init__(self):
        super().__init__(DeliveryPartner)

    @staticmethod
    def get_locked_by_user(user):
        return DeliveryPartner.objects.select_for_update().get(user=user)

    @staticmethod
    def get_by_id(pk: str, prefetch: list = None, select_related: list = None) -> DeliveryPartner:
        qs = DeliveryPartner.objects.all()
        if select_related:
            qs = qs.select_related(*select_related)
        if prefetch:
            qs = qs.prefetch_related(*prefetch)
        return qs.get(pk=pk)

    @staticmethod
    def get_by_user(user, prefetch: list = None) -> DeliveryPartner:
        qs = DeliveryPartner.objects.all()
        if prefetch:
            qs = qs.prefetch_related(*prefetch)
        return qs.get(user=user)

    @staticmethod
    def get_all(search: str = None, is_approved: bool = None, status_filter: str = None) -> QuerySet[DeliveryPartner]:
        qs = DeliveryPartner.objects.select_related("user").order_by("-created_at")

        if search:
            qs = (
                qs.filter(user__username__icontains=search)
                | DeliveryPartner.objects.filter(user__email__icontains=search)
                | DeliveryPartner.objects.filter(user__first_name__icontains=search)
            ).distinct()

        if is_approved is not None:
            qs = qs.filter(is_approved=is_approved)

        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs

    @staticmethod
    def save(instance: DeliveryPartner, update_fields: list = None) -> DeliveryPartner:
        instance.save(update_fields=update_fields)
        return instance

    @staticmethod
    def get_base_queryset():
        """Return the base queryset for DeliveryPartner without any filters."""
        return DeliveryPartner.objects.all()

    @staticmethod
    def tracking_snapshot(order_id):
        return DeliveryPartner.objects.filter(
            user__deliveries__id=order_id,
            user__deliveries__status__in=['ready', 'picked_up', 'on_the_way'],
        ).first()

    @staticmethod
    def save_location(instance, latitude, longitude):
        return DeliveryPartnerRepository.update(
            instance, current_latitude=latitude, current_longitude=longitude,
            location_updated_at=timezone.now(),
        )

    @staticmethod
    def update(instance: DeliveryPartner, **kwargs) -> DeliveryPartner:
        """Apply field updates to ``instance`` and save."""
        for field, value in kwargs.items():
            setattr(instance, field, value)
        instance.save(update_fields=list(kwargs.keys()) + ["updated_at"])
        return instance

    @staticmethod
    def delete(instance: DeliveryPartner) -> None:
        instance.delete()
