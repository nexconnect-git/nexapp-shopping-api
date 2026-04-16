"""Token-based password reset for customers."""

import secrets
from datetime import timedelta

from django.db import models
from django.utils import timezone

from accounts.models.user import User


class PasswordResetToken(models.Model):
    """Single-use token that authorises a password reset.

    A token is valid for 1 hour and is consumed on first use.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token = models.CharField(max_length=96, unique=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    TOKEN_LIFETIME_HOURS = 1

    class Meta:
        app_label = 'accounts'
        ordering = ['-created_at']

    def __str__(self):
        return f"PasswordReset for {self.user.email} (used={self.used})"

    @property
    def is_valid(self) -> bool:
        return not self.used and timezone.now() < self.expires_at

    @classmethod
    def create_for_user(cls, user) -> 'PasswordResetToken':
        """Invalidate prior unused tokens for this user and create a fresh one."""
        cls.objects.filter(user=user, used=False).update(used=True)
        return cls.objects.create(
            user=user,
            token=secrets.token_urlsafe(64),
            expires_at=timezone.now() + timedelta(hours=cls.TOKEN_LIFETIME_HOURS),
        )
