from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from helpers.cache_helpers import invalidate_catalog_cache
from products.models import Category, Product, ProductImage
from products.models.catalog import CatalogProduct, CatalogProductImage, VendorCatalogGrant


@receiver([post_save, post_delete], sender=Category)
@receiver([post_save, post_delete], sender=Product)
@receiver([post_save, post_delete], sender=ProductImage)
@receiver([post_save, post_delete], sender=CatalogProduct)
@receiver([post_save, post_delete], sender=CatalogProductImage)
@receiver([post_save, post_delete], sender=VendorCatalogGrant)
def invalidate_catalog_cache_for_product_change(sender, **kwargs):
    invalidate_catalog_cache()
