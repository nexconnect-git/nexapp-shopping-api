"""Hashed single-use password reset tokens for all account roles."""


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
