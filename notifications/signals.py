from django.dispatch import receiver
from backend.events import order_placed, order_cancelled, vendor_approved, order_status_updated
from .models import Notification

@receiver(order_placed)
def notify_order_placed(sender, order, **kwargs):
    Notification.objects.create(
        user=order.vendor.user,
        title="New Order Received",
        message=f"You have a new order #{order.order_number} worth ${order.total}.",
        notification_type="order",
        data={"order_id": str(order.id), "order_number": order.order_number},
    )
    Notification.objects.create(
        user=order.customer,
        title="Order Placed Successfully",
        message=f"Your order #{order.order_number} from {order.vendor.store_name} has been placed! We'll notify you once it's confirmed.",
        notification_type="order",
        data={"order_id": str(order.id), "order_number": order.order_number},
    )

@receiver(order_cancelled)
def notify_order_cancelled(sender, order, **kwargs):
    Notification.objects.create(
        user=order.vendor.user,
        title="Order Cancelled",
        message=f"Order #{order.order_number} has been cancelled by the customer.",
        notification_type="order",
        data={"order_id": str(order.id), "order_number": order.order_number},
    )

@receiver(order_status_updated)
def notify_order_status(sender, order, new_status, old_status, **kwargs):
    if new_status == "on_the_way":
        Notification.objects.create(
            user=order.customer,
            title="Order On the Way",
            message=f"Your order #{order.order_number} is on the way to you!",
            notification_type="delivery",
            data={"order_id": str(order.id), "order_number": order.order_number},
        )
    elif new_status == "delivered":
        Notification.objects.create(
            user=order.customer,
            title="Order Delivered",
            message=f"Your order #{order.order_number} has been delivered successfully. Enjoy!",
            notification_type="delivery",
            data={"order_id": str(order.id), "order_number": order.order_number},
        )
    elif new_status == "reassigned":
        # Delivery cancelled -> re-searching
        Notification.objects.create(
            user=order.customer,
            title="Delivery Partner Unavailable",
            message=f"Your delivery partner for order #{order.order_number} cancelled. Finding a new one…",
            notification_type="delivery",
            data={"order_id": str(order.id)},
        )
