"""Customer wallet models."""

import uuid
from django.db import models
from accounts.models.user import User


class Wallet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'accounts'

    def __str__(self):
        return f"Wallet({self.user.username}) ₹{self.balance}"


class WalletTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    )
    SOURCES = (
        ('topup', 'Top-up'),
        ('refund', 'Refund'),
        ('order_payment', 'Order Payment'),
        ('admin', 'Admin Adjustment'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    source = models.CharField(max_length=20, choices=SOURCES)
    reference_id = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'accounts'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.transaction_type} ₹{self.amount} ({self.source})"
