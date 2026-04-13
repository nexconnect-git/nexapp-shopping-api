import uuid
from django.db import models
from accounts.models import User
from vendors.models.vendor import Vendor

VENDOR_TYPE_CHOICES = (
    ('individual', 'Individual'),
    ('company', 'Company'),
    ('partnership', 'Partnership'),
)

KYC_STATUS_CHOICES = (
    ('pending',  'Pending'),
    ('verified', 'Verified'),
    ('rejected', 'Rejected'),
)

ONBOARDING_STATUS_CHOICES = (
    ('draft',        'Draft'),
    ('submitted',    'Submitted'),
    ('under_review', 'Under Review'),
    ('approved',     'Approved'),
    ('rejected',     'Rejected'),
)


class VendorOnboarding(models.Model):
    """
    Captures full onboarding details: legal identity, compliance docs references,
    KYC status, and overall onboarding workflow state.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.OneToOneField(Vendor, on_delete=models.CASCADE, related_name='onboarding')

    # ── Basic / legal identity ────────────────────────────────────────────────
    legal_name            = models.CharField(max_length=255, blank=True)
    vendor_type           = models.CharField(max_length=20, choices=VENDOR_TYPE_CHOICES, default='individual')
    contact_person_name   = models.CharField(max_length=200, blank=True)
    contact_person_email  = models.EmailField(blank=True)
    contact_person_phone  = models.CharField(max_length=15, blank=True)
    gst_registered        = models.BooleanField(default=False)

    # ── Legal & compliance numbers ────────────────────────────────────────────
    pan_number        = models.CharField(max_length=10, blank=True)
    gstin             = models.CharField(max_length=15, blank=True)
    cin_udyam         = models.CharField(max_length=50, blank=True, help_text='CIN or Udyam Registration number')
    fssai_license     = models.CharField(max_length=50, blank=True)
    trademark_number  = models.CharField(max_length=50, blank=True)

    # ── Additional business addresses (JSON list of address dicts) ────────────
    business_addresses = models.JSONField(default=list, blank=True)

    # ── KYC & onboarding workflow ─────────────────────────────────────────────
    kyc_status          = models.CharField(max_length=20, choices=KYC_STATUS_CHOICES, default='pending')
    onboarding_status   = models.CharField(max_length=20, choices=ONBOARDING_STATUS_CHOICES, default='draft')
    rejection_reason    = models.TextField(blank=True)

    submitted_at  = models.DateTimeField(null=True, blank=True)
    reviewed_at   = models.DateTimeField(null=True, blank=True)
    reviewed_by   = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reviewed_onboardings'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'vendors'

    def __str__(self):
        return f'Onboarding — {self.vendor.store_name} [{self.onboarding_status}]'
