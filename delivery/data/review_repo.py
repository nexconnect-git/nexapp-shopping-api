from django.db.models import QuerySet
from delivery.models import DeliveryReview


class DeliveryReviewRepository:
    """Repository for DeliveryReview database operations."""

    @staticmethod
    def get_all() -> QuerySet[DeliveryReview]:
        return DeliveryReview.objects.all()

    @staticmethod
    def get_by_partner(partner_id) -> QuerySet[DeliveryReview]:
        return DeliveryReview.objects.filter(delivery_partner_id=partner_id)
