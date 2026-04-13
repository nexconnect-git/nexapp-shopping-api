import uuid
from django.db import models
from products.models.product import Product


class ProductReview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'products'
        unique_together = ('product', 'customer')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        reviews = self.product.reviews.all()
        self.product.average_rating = sum(r.rating for r in reviews) / reviews.count()
        self.product.total_ratings = reviews.count()
        self.product.save(update_fields=['average_rating', 'total_ratings'])
