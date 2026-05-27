from django.db.models import Q
from django.utils import timezone

from orders.models import CustomerContentBlock
from vendors.data.base import BaseRepository


class CustomerContentBlockRepository(BaseRepository):
    def __init__(self):
        super().__init__(CustomerContentBlock)

    def get_active(self):
        now = timezone.now()
        return CustomerContentBlock.objects.filter(
            is_active=True,
        ).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
        ).filter(
            Q(ends_at__isnull=True) | Q(ends_at__gte=now),
        ).order_by('placement', 'display_order', 'created_at')

    def get_all_ordered(self):
        return CustomerContentBlock.objects.all().order_by(
            'placement',
            'display_order',
            '-updated_at',
        )
