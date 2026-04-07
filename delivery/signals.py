from django.dispatch import receiver
from backend.events import order_placed
from .models import DeliveryAssignment
from .tasks import search_and_notify_partners

@receiver(order_placed)
def start_delivery_assignment_process(sender, order, **kwargs):
    """
    Listens for 'order_placed' event and asynchronously kicks off
    delivery partner discovery.
    """
    assignment = DeliveryAssignment.objects.create(order=order)
    search_and_notify_partners.delay(str(assignment.id))
