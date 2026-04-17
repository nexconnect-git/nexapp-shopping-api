"""Referral program models."""

import uuid
import secrets
from django.db import models
from accounts.models.user import User

REFERRAL_BONUS_POINTS = 100  # points awarded to referrer when referee places first order


class ReferralCode(models.Model):
    """One-to-one with User. Each user gets a unique shareable code."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='referral_code')
    code = models.CharField(max_length=12, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'accounts'

    def __str__(self):
        return f"{self.user.username} → {self.code}"

    @classmethod
    def get_or_create_for_user(cls, user) -> 'ReferralCode':
        try:
            return cls.objects.get(user=user)
        except cls.DoesNotExist:
            code = secrets.token_urlsafe(8)[:8].upper()
            while cls.objects.filter(code=code).exists():
                code = secrets.token_urlsafe(8)[:8].upper()
            return cls.objects.create(user=user, code=code)


class Referral(models.Model):
    """Records when a new user signs up via a referral code."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_made')
    referee = models.OneToOneField(User, on_delete=models.CASCADE, related_name='referred_by')
    bonus_awarded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'accounts'

    def __str__(self):
        return f"{self.referrer.username} referred {self.referee.username}"
