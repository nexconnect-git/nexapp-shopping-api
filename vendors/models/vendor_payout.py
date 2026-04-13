import uuid
from django.db import models
from accounts.models import User
from vendors.models.vendor import Vendor

PAYOUT_STATUS_CHOICES = (
    ('pending_approval', 'Pending Vendor Approval'),
    ('approved',         'Approved by Vendor'),
    ('scheduled',        'Scheduled for Processing'),
    ('paid',             'Payment Dispatched — Awaiting Verification'),
    ('verified',         'Verified'),
    ('failed',           'Failed'),
)


class VendorPayout(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='payouts')
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    gross_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_commission = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_payout = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=PAYOUT_STATUS_CHOICES, default='pending_approval')
    transaction_ref = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    # Approval & verification lifecycle fields
    vendor_approved_at = models.DateTimeField(null=True, blank=True)
    payment_sent_at = models.DateTimeField(null=True, blank=True)
    vendor_verified_at = models.DateTimeField(null=True, blank=True)
    vendor_rejection_reason = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'vendors'
        ordering = ['-period_start']

    def __str__(self):
        return f"Payout {self.period_start.date()} to {self.period_end.date()} — {self.vendor.store_name}"


class DeliveryPartnerPayout(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery_partner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='delivery_payouts')
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    total_deliveries = models.IntegerField(default=0)
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=PAYOUT_STATUS_CHOICES, default='pending_approval')
    transaction_ref = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    # Approval & verification lifecycle fields
    partner_approved_at = models.DateTimeField(null=True, blank=True)
    payment_sent_at = models.DateTimeField(null=True, blank=True)
    partner_verified_at = models.DateTimeField(null=True, blank=True)
    partner_rejection_reason = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'vendors'
        ordering = ['-period_start']

    def __str__(self):
        return f"Payout {self.period_start.date()} to {self.period_end.date()} — {self.delivery_partner.get_full_name()}"
