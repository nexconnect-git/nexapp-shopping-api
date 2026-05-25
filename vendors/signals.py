from django.dispatch import receiver
from django.db.models.signals import post_delete, post_save

from backend.events import order_placed, order_status_updated
from helpers.cache_helpers import invalidate_catalog_cache
from vendors.models import Vendor, VendorHoliday, VendorServiceableArea
from vendors.realtime import broadcast_order_event


@receiver(order_placed)
def broadcast_vendor_order_created(sender, order, **kwargs):
    broadcast_order_event(order, "order_created")


@receiver(order_status_updated)
def broadcast_vendor_order_updated(sender, order, **kwargs):
    broadcast_order_event(order, "order_updated")


@receiver([post_save, post_delete], sender=Vendor)
@receiver([post_save, post_delete], sender=VendorHoliday)
@receiver([post_save, post_delete], sender=VendorServiceableArea)
def invalidate_catalog_cache_for_vendor_change(sender, **kwargs):
    invalidate_catalog_cache()
