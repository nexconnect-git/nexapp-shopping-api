import uuid
from django.db import models
from accounts.models import User
from vendors.models.vendor import Vendor

DOCUMENT_TYPE_CHOICES = (
    ('pan_card',             'PAN Card'),
    ('gstin_certificate',    'GSTIN Certificate'),
    ('identity_proof',       'Identity Proof (Aadhaar / Passport)'),
    ('address_proof',        'Address Proof'),
    ('cancelled_cheque',     'Cancelled Cheque'),
    ('fssai_license',        'FSSAI License'),
    ('trademark',            'Trademark Certificate'),
    ('business_registration','Business Registration (CIN / Udyam)'),
)

DOCUMENT_STATUS_CHOICES = (
    ('pending',  'Pending Review'),
    ('verified', 'Verified'),
    ('rejected', 'Rejected'),
)


class VendorDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor            = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='documents')
    document_type     = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES)
    file              = models.FileField(upload_to='vendor_documents/')
    original_filename = models.CharField(max_length=255, blank=True)
    file_size_bytes   = models.IntegerField(default=0)
    status            = models.CharField(max_length=20, choices=DOCUMENT_STATUS_CHOICES, default='pending')
    rejection_reason  = models.TextField(blank=True)
    verified_by       = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='verified_documents'
    )
    verified_at  = models.DateTimeField(null=True, blank=True)
    uploaded_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'vendors'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.get_document_type_display()} — {self.vendor.store_name}'
