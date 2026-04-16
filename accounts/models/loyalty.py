"""Customer loyalty points models."""

import uuid
from django.db import models
from accounts.models.user import User


class LoyaltyAccount(models.Model):
    """One-to-one with User. Tracks total points balance."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='loyalty')
    points = models.IntegerField(default=0)
    lifetime_points = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'accounts'

    def __str__(self):
        return f"Loyalty({self.user.username}) {self.points}pts"


class LoyaltyTransaction(models.Model):
    TYPES = (
        ('earn', 'Earned'),
        ('redeem', 'Redeemed'),
        ('expire', 'Expired'),
        ('adjust', 'Admin Adjustment'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(LoyaltyAccount, on_delete=models.CASCADE, related_name='transactions')
    points = models.IntegerField()
    transaction_type = models.CharField(max_length=10, choices=TYPES)
    reference_id = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'accounts'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.transaction_type} {self.points}pts"
