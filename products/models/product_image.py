import uuid
from django.db import models
from products.models.product import Product


class ProductImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    is_primary = models.BooleanField(default=False)
    is_ai_generated = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)

    class Meta:
        app_label = 'products'
        ordering = ['display_order']
