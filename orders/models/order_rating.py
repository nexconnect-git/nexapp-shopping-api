import uuid
from django.db import models
from accounts.models import User


class OrderRating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='rating')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='order_ratings')
    delivery_partner = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_ratings'
    )
    # Legacy aggregate rating for backwards compatibility with older clients.
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    vendor_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    vendor_comment = models.TextField(blank=True, default='')
    delivery_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    delivery_comment = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'orders'

    def __str__(self):
        return f"Rating for {self.order.order_number}"
