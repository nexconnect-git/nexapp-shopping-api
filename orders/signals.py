from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from helpers.cache_helpers import invalidate_catalog_cache
from orders.models import Coupon, CustomerContentBlock, PlatformBanner, PlatformSetting


@receiver([post_save, post_delete], sender=Coupon)
@receiver([post_save, post_delete], sender=CustomerContentBlock)
@receiver([post_save, post_delete], sender=PlatformBanner)
@receiver([post_save, post_delete], sender=PlatformSetting)
def invalidate_catalog_cache_for_order_content_change(sender, **kwargs):
    invalidate_catalog_cache()
