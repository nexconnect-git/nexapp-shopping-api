import uuid
from django.db import models
from vendors.models.vendor import Vendor


class VendorWalletTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    )
    SOURCES = (
        ('order_earning', 'Order Earning'),
        ('payout_withdrawal', 'Payout Withdrawal'),
        ('admin_adjustment', 'Admin Adjustment'),
        ('refund_deduction', 'Refund Deduction'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='wallet_transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    source = models.CharField(max_length=20, choices=SOURCES)
    reference_id = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField(blank=True)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Running balance after this transaction")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'vendors'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.transaction_type} ₹{self.amount} ({self.source}) - {self.vendor.store_name}"
