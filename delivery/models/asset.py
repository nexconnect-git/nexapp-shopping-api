import uuid
from django.db import models
from delivery.models.delivery_partner import DeliveryPartner


class Asset(models.Model):
    ASSET_TYPES = [
        ('vehicle', 'Vehicle'),
        ('tracking_device', 'Tracking Device'),
        ('uniform', 'Uniform'),
        ('equipment', 'Equipment'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Under Maintenance'),
        ('retired', 'Retired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    asset_type = models.CharField(max_length=30, choices=ASSET_TYPES)
    serial_number = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    assigned_to = models.ForeignKey(
        DeliveryPartner, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assets'
    )
    purchase_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'delivery'

    def __str__(self):
        return f"{self.name} ({self.asset_type})"
