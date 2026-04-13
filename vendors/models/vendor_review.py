import uuid
from django.db import models
from accounts.models import User
from vendors.models.vendor import Vendor

class VendorReview(models.Model):
    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor   = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    rating   = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment  = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'vendors'
        unique_together = ('vendor', 'customer')

    def __str__(self):
        return f'{self.customer.username} — {self.vendor.store_name} ({self.rating})'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        reviews = self.vendor.reviews.all()
        self.vendor.average_rating = sum(r.rating for r in reviews) / reviews.count()
        self.vendor.total_ratings  = reviews.count()
        self.vendor.save(update_fields=['average_rating', 'total_ratings'])
