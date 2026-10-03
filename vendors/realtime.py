import logging
import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from orders.serializers import OrderSerializer
from orders.data.order_repo import OrderRepository
from rest_framework.renderers import JSONRenderer

logger = logging.getLogger(__name__)


def broadcast_vendor_event(vendor_id, event_type: str, payload: dict):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            f"vendor_ops_{vendor_id}",
            {
                "type": "vendor.event",
                "event": event_type,
                "payload": json.loads(JSONRenderer().render(payload)),
            },
        )
    except Exception:
        logger.exception("Vendor event delivery failed for %s", vendor_id)


def broadcast_order_event(order, event_type: str = "order_updated"):
    order = OrderRepository.get_by_id(order.pk)
    broadcast_vendor_event(
        order.vendor_id,
        event_type,
        {"order": OrderSerializer(order, context={'vendor_scope': True}).data},
    )
