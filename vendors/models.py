import uuid
from django.db import models
from accounts.models import User


# ── Choices ───────────────────────────────────────────────────────────────────

VENDOR_TYPE_CHOICES = (
    ('individual', 'Individual'),
    ('company', 'Company'),
    ('partnership', 'Partnership'),
)

FULFILLMENT_TYPE_CHOICES = (
    ('vendor', 'Vendor Fulfilled'),
    ('platform', 'Platform Fulfilled'),
)

VENDOR_TIER_CHOICES = (
    ('basic', 'Basic'),
    ('silver', 'Silver'),
    ('gold', 'Gold'),
    ('platinum', 'Platinum'),
)

SETTLEMENT_CYCLE_CHOICES = (
    ('T+1',  'Next Day (T+1)'),
    ('T+7',  'Weekly (T+7)'),
    ('T+15', 'Fortnightly (T+15)'),
    ('T+30', 'Monthly (T+30)'),
)

ACCOUNT_TYPE_CHOICES = (
    ('savings', 'Savings'),
    ('current', 'Current'),
)

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


# ── Vendor ────────────────────────────────────────────────────────────────────

class Vendor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    STATUS_CHOICES = (
        ('pending',   'Pending Approval'),
        ('approved',  'Approved'),
        ('rejected',  'Rejected'),
        ('suspended', 'Suspended'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor_profile')

    # ── Core store info ───────────────────────────────────────────────────────
    store_name   = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    logo         = models.ImageField(upload_to='vendor_logos/',   blank=True, null=True)
    banner       = models.ImageField(upload_to='vendor_banners/', blank=True, null=True)
    phone        = models.CharField(max_length=15)
    email        = models.EmailField()
    address      = models.CharField(max_length=255)
    city         = models.CharField(max_length=100)
    state        = models.CharField(max_length=100)
    postal_code  = models.CharField(max_length=10)
    latitude     = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    longitude    = models.DecimalField(max_digits=9, decimal_places=6, default=0)

    # ── Classification ────────────────────────────────────────────────────────
    vendor_type  = models.CharField(max_length=20, choices=VENDOR_TYPE_CHOICES, default='individual', blank=True)
    vendor_tier  = models.CharField(max_length=20, choices=VENDOR_TIER_CHOICES, default='basic', blank=True)

    # ── Approval / ratings ────────────────────────────────────────────────────
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_featured    = models.BooleanField(default=False)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_ratings  = models.IntegerField(default=0)
    wallet_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ── Operating hours ───────────────────────────────────────────────────────
    is_open       = models.BooleanField(default=True)
    opening_time  = models.TimeField(default='09:00')
    closing_time  = models.TimeField(default='22:00')

    # ── Delivery settings ─────────────────────────────────────────────────────
    min_order_amount    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_radius_km  = models.DecimalField(max_digits=5,  decimal_places=2, default=5.0)

    # ── Fulfillment ───────────────────────────────────────────────────────────
    fulfillment_type         = models.CharField(max_length=20, choices=FULFILLMENT_TYPE_CHOICES, default='vendor', blank=True)
    dispatch_sla_hours       = models.IntegerField(default=24)
    return_policy            = models.TextField(blank=True)
    packaging_preferences    = models.TextField(blank=True)
    auto_order_acceptance    = models.BooleanField(default=False)
    cancellation_rules       = models.TextField(blank=True)

    # ── Stock check gate (admin-controlled) ───────────────────────────────────
    require_stock_check      = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.store_name


# ── VendorOnboarding ──────────────────────────────────────────────────────────

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

    def __str__(self):
        return f'Onboarding — {self.vendor.store_name} [{self.onboarding_status}]'


# ── VendorBankDetails ─────────────────────────────────────────────────────────

class VendorBankDetails(models.Model):
    """
    Bank and payment settings for a vendor.
    Account number is stored encrypted via Fernet (AES-128-CBC).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.OneToOneField(Vendor, on_delete=models.CASCADE, related_name='bank_details')

    account_holder_name   = models.CharField(max_length=200, blank=True)
    # Encrypted account number — use get_account_number() / set_account_number()
    account_number_enc    = models.TextField(blank=True)
    ifsc_code             = models.CharField(max_length=11, blank=True)
    bank_name             = models.CharField(max_length=100, blank=True)
    branch_name           = models.CharField(max_length=100, blank=True)
    account_type          = models.CharField(max_length=10, choices=ACCOUNT_TYPE_CHOICES, default='current', blank=True)
    upi_id                = models.CharField(max_length=100, blank=True)
    settlement_cycle      = models.CharField(max_length=5, choices=SETTLEMENT_CYCLE_CHOICES, default='T+7', blank=True)
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_verified           = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_account_number(self, plaintext: str):
        from .utils import encrypt_value
        self.account_number_enc = encrypt_value(plaintext)

    def get_account_number(self) -> str:
        from .utils import decrypt_value
        return decrypt_value(self.account_number_enc)

    @property
    def masked_account_number(self) -> str:
        from .utils import mask_account_number, decrypt_value
        return mask_account_number(decrypt_value(self.account_number_enc))

    def __str__(self):
        return f'Bank — {self.vendor.store_name}'


# ── VendorDocument ────────────────────────────────────────────────────────────

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
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.get_document_type_display()} — {self.vendor.store_name}'


# ── VendorServiceableArea ─────────────────────────────────────────────────────

class VendorServiceableArea(models.Model):
    id      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor  = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='serviceable_areas')
    pincode = models.CharField(max_length=10)
    city    = models.CharField(max_length=100, blank=True)
    state   = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('vendor', 'pincode')
        ordering = ['pincode']

    def __str__(self):
        return f'{self.pincode} — {self.vendor.store_name}'


# ── VendorHoliday ─────────────────────────────────────────────────────────────

class VendorHoliday(models.Model):
    id     = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='holidays')
    date   = models.DateField()
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ('vendor', 'date')
        ordering = ['date']

    def __str__(self):
        return f'{self.date} — {self.vendor.store_name}'


# ── VendorAuditLog ────────────────────────────────────────────────────────────

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
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} — {self.vendor.store_name}'


# ── VendorReview ──────────────────────────────────────────────────────────────

class VendorReview(models.Model):
    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor   = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    rating   = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment  = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('vendor', 'customer')

    def __str__(self):
        return f'{self.customer.username} — {self.vendor.store_name} ({self.rating})'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        reviews = self.vendor.reviews.all()
        self.vendor.average_rating = sum(r.rating for r in reviews) / reviews.count()
        self.vendor.total_ratings  = reviews.count()
        self.vendor.save(update_fields=['average_rating', 'total_ratings'])


# ── Payouts ───────────────────────────────────────────────────────────────────

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
        ordering = ['-period_start']

    def __str__(self):
        return f"Payout {self.period_start.date()} to {self.period_end.date()} — {self.delivery_partner.get_full_name()}"

