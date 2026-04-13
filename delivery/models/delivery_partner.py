import uuid
from django.db import models
from accounts.models import User


class DeliveryPartner(models.Model):
    VEHICLE_CHOICES = (
        ('bicycle', 'Bicycle'),
        ('motorcycle', 'Motorcycle'),
        ('car', 'Car'),
        ('van', 'Van'),
    )
    STATUS_CHOICES = (
        ('offline', 'Offline'),
        ('available', 'Available'),
        ('on_delivery', 'On Delivery'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='delivery_profile')
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_CHOICES)
    vehicle_number = models.CharField(max_length=20, blank=True)
    license_number = models.CharField(max_length=50)
    id_proof = models.ImageField(upload_to='delivery/id_proofs/', blank=True, null=True)
    is_approved = models.BooleanField(default=False)
    is_available = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline')
    current_latitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_deliveries = models.IntegerField(default=0)
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    wallet_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'delivery'

    def __str__(self):
        return f"{self.user.username} - {self.vehicle_type}"
