import uuid

from django.conf import settings
from django.db import models


class CustomerRecommendationSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='customer_recommendation_snapshot',
    )
    recommended_product_ids = models.JSONField(default=list, blank=True)
    flash_deal_product_ids = models.JSONField(default=list, blank=True)
    recommended_store_ids = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'orders'
        indexes = [
            models.Index(fields=['user', '-generated_at'], name='cust_rec_user_generated_idx'),
        ]

    def __str__(self):
        return f'Recommendations for {self.user_id}'
