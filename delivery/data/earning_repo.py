from django.db.models import QuerySet, Sum
from delivery.models import DeliveryEarning
from vendors.data.base import BaseRepository


class DeliveryEarningRepository(BaseRepository):
    """Repository for DeliveryEarning database operations."""

    def __init__(self):
        super().__init__(DeliveryEarning)

    @staticmethod
    def get_by_partner(partner) -> QuerySet[DeliveryEarning]:
        return DeliveryEarning.objects.filter(delivery_partner=partner)

    @staticmethod
    def create(partner, order, amount) -> DeliveryEarning:
        return DeliveryEarning.objects.create(
            delivery_partner=partner,
            order=order,
            amount=amount
        )

    @staticmethod
    def get_or_create(partner, order, amount):
        return DeliveryEarning.objects.get_or_create(
            order=order, defaults={'delivery_partner': partner, 'amount': amount},
        )

    @staticmethod
    def calculate_earnings(partner, start_date=None, end_date=None) -> tuple[float, int]:
        qs = DeliveryEarning.objects.filter(delivery_partner=partner)
        if start_date:
            qs = qs.filter(created_at__gte=start_date + "T00:00:00Z")
        if end_date:
            qs = qs.filter(created_at__lte=end_date + "T23:59:59Z")

        total = qs.aggregate(total_amount=Sum("amount"))["total_amount"] or 0
        count = qs.count()
        return float(total), count
