import random
from datetime import timedelta

from django.db import models
from django.utils import timezone

from accounts.models.user import User


class EmailVerification(models.Model):
    """One-time OTP record for verifying a user's email address.

    A new 6-digit OTP is created on each ``send_verification_email`` call.
    Previous unused OTPs for the same user are invalidated automatically.
    OTPs expire after 15 minutes.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_verifications')
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    OTP_LIFETIME_MINUTES = 15

    class Meta:
        app_label = 'accounts'
        ordering = ['-created_at']

    def __str__(self):
        return f"OTP for {self.user.email} (used={self.is_used})"

    def save(self, *args, **kwargs):
        if not self.pk and not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=self.OTP_LIFETIME_MINUTES)
        super().save(*args, **kwargs)

    @property
    def is_valid(self) -> bool:
        return not self.is_used and timezone.now() < self.expires_at

    @classmethod
    def create_for_user(cls, user) -> 'EmailVerification':
        """Invalidate all previous OTPs for the user and create a fresh one."""
        cls.objects.filter(user=user, is_used=False).update(is_used=True)
        otp = f"{random.randint(0, 999999):06d}"
        return cls.objects.create(user=user, otp=otp)
