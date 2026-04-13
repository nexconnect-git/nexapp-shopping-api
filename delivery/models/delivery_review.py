import uuid
from django.db import models
from accounts.models import User
from delivery.models.delivery_partner import DeliveryPartner


class DeliveryReview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery_partner = models.ForeignKey(DeliveryPartner, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'delivery'
        unique_together = ('delivery_partner', 'order')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        reviews = self.delivery_partner.reviews.all()
        self.delivery_partner.average_rating = sum(r.rating for r in reviews) / reviews.count()
        self.delivery_partner.total_deliveries = reviews.count()
        self.delivery_partner.save(update_fields=['average_rating', 'total_deliveries'])
