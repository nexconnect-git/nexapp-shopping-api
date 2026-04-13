import uuid
from django.db import models
from accounts.models import User
from vendors.models.vendor import Vendor

AUDIT_ACTION_CHOICES = (
    ('created',               'Vendor Created'),
    ('profile_updated',       'Profile Updated'),
    ('status_changed',        'Status Changed'),
    ('document_uploaded',     'Document Uploaded'),
    ('document_verified',     'Document Verified'),
    ('document_rejected',     'Document Rejected'),
    ('bank_updated',          'Bank Details Updated'),
    ('bank_verified',         'Bank Details Verified'),
    ('kyc_submitted',         'KYC Submitted'),
    ('kyc_approved',          'KYC Approved'),
    ('kyc_rejected',          'KYC Rejected'),
    ('onboarding_submitted',  'Onboarding Submitted'),
    ('onboarding_approved',   'Onboarding Approved'),
    ('onboarding_rejected',   'Onboarding Rejected'),
    ('serviceable_area_added','Serviceable Area Added'),
    ('holiday_added',         'Holiday Added'),
)


class VendorAuditLog(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor       = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='audit_logs')
    action       = models.CharField(max_length=30, choices=AUDIT_ACTION_CHOICES)
    description  = models.TextField()
    performed_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='audit_actions'
    )
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    metadata     = models.JSONField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'vendors'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} — {self.vendor.store_name}'
