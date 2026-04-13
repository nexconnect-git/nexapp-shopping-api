import uuid
from django.db import models
from vendors.models.vendor import Vendor

ACCOUNT_TYPE_CHOICES = (
    ('savings', 'Savings'),
    ('current', 'Current'),
)

SETTLEMENT_CYCLE_CHOICES = (
    ('T+1',  'Next Day (T+1)'),
    ('T+7',  'Weekly (T+7)'),
    ('T+15', 'Fortnightly (T+15)'),
    ('T+30', 'Monthly (T+30)'),
)


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

    class Meta:
        app_label = 'vendors'

    def set_account_number(self, plaintext: str):
        from helpers.encryption import encrypt_value
        self.account_number_enc = encrypt_value(plaintext)

    def get_account_number(self) -> str:
        from helpers.encryption import decrypt_value
        return decrypt_value(self.account_number_enc)

    @property
    def masked_account_number(self) -> str:
        from helpers.encryption import mask_account_number, decrypt_value
        return mask_account_number(decrypt_value(self.account_number_enc))

    def __str__(self):
        return f'Bank — {self.vendor.store_name}'
