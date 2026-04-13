import uuid
from django.db import models
from vendors.models.vendor import Vendor


class VendorServiceableArea(models.Model):
    id      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor  = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='serviceable_areas')
    pincode = models.CharField(max_length=10)
    city    = models.CharField(max_length=100, blank=True)
    state   = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'vendors'
        unique_together = ('vendor', 'pincode')
        ordering = ['pincode']

    def __str__(self):
        return f'{self.pincode} — {self.vendor.store_name}'
