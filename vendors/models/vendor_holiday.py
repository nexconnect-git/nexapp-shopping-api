import uuid
from django.db import models
from vendors.models.vendor import Vendor


class VendorHoliday(models.Model):
    id     = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='holidays')
    date   = models.DateField()
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        app_label = 'vendors'
        unique_together = ('vendor', 'date')
        ordering = ['date']

    def __str__(self):
        return f'{self.date} — {self.vendor.store_name}'
