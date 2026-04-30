from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from orders.serializers import OrderSerializer


def broadcast_vendor_event(vendor_id, event_type: str, payload: dict):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"vendor_ops_{vendor_id}",
        {
            "type": "vendor.event",
            "event": event_type,
            "payload": payload,
        },
    )


def broadcast_order_event(order, event_type: str = "order_updated"):
    broadcast_vendor_event(
        order.vendor_id,
        event_type,
        {"order": OrderSerializer(order).data},
    )
