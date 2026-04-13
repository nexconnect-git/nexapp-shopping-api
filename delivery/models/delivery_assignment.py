import uuid
from django.db import models
from django.utils import timezone
from delivery.models.delivery_partner import DeliveryPartner


class DeliveryAssignment(models.Model):
    """Tracks the radius-based partner search for an order."""

    STATUS_CHOICES = [
        ('searching', 'Searching'),
        ('notified', 'Partners Notified'),
        ('accepted', 'Accepted'),
        ('timed_out', 'Timed Out - No Response'),
        ('failed', 'Failed - No Partners Found'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        'orders.Order', on_delete=models.CASCADE, related_name='assignment'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='searching')
    current_radius_km = models.FloatField(default=2.0)
    max_radius_km = models.FloatField(default=20.0)
    notified_partners = models.ManyToManyField(
        DeliveryPartner, blank=True, related_name='notified_assignments'
    )
    rejected_partners = models.ManyToManyField(
        DeliveryPartner, blank=True, related_name='rejected_assignments'
    )
    accepted_partner = models.ForeignKey(
        DeliveryPartner, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='accepted_assignment'
    )
    last_search_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'delivery'

    def __str__(self):
        return f"Assignment for {self.order.order_number} [{self.status}]"
