import asyncio
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from accounts.models import User
from vendors.models import Vendor
from delivery.models import DeliveryPartner
from orders.models import Order, OrderIssue
from support.models import SupportTicket

def trigger_admin_stats_update():
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            'admin_stats',
            {
                'type': 'update_stats'
            }
        )

@receiver([post_save, post_delete], sender=User)
@receiver([post_save, post_delete], sender=Vendor)
@receiver([post_save, post_delete], sender=DeliveryPartner)
@receiver([post_save, post_delete], sender=Order)
@receiver([post_save, post_delete], sender=OrderIssue)
@receiver([post_save, post_delete], sender=SupportTicket)
def handle_model_changes(sender, instance, **kwargs):
    trigger_admin_stats_update()
