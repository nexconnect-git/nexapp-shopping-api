import uuid
from django.db import models
from accounts.models import User
from vendors.models import Vendor
from orders.models import Order

INVOICE_TYPE_CHOICES = (
    ('customer_receipt',    'Customer Receipt'),
    ('vendor_settlement',   'Vendor Settlement'),
    ('delivery_payout',     'Delivery Partner Payout'),
)


class Invoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=30, unique=True, editable=False)
    invoice_type = models.CharField(max_length=25, choices=INVOICE_TYPE_CHOICES)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    recipient = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    pdf_file = models.FileField(upload_to='invoices/', null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'invoices'
        ordering = ['-issued_at']

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            from invoices.helpers.invoice_helpers import generate_invoice_number
            self.invoice_number = generate_invoice_number(self.invoice_type)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.invoice_number} [{self.get_invoice_type_display()}]'
