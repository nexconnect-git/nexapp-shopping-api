from django.dispatch import receiver
from backend.events import order_placed

@receiver(order_placed)
def generate_invoice_for_order(sender, order, **kwargs):
    """
    Listens for 'order_placed' event and delegates to a background
    task to generate the invoice PDF and send it via email.
    """
    from notifications.tasks import process_order_invoice_and_email
    process_order_invoice_and_email.delay(str(order.id))
