from django.dispatch import receiver

from backend.events import order_placed, order_status_updated
from vendors.realtime import broadcast_order_event


@receiver(order_placed)
def broadcast_vendor_order_created(sender, order, **kwargs):
    broadcast_order_event(order, "order_created")


@receiver(order_status_updated)
def broadcast_vendor_order_updated(sender, order, **kwargs):
    broadcast_order_event(order, "order_updated")
