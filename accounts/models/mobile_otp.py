import random
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone


class MobileOTP(models.Model):
    PURPOSE_LOGIN = 'login'
    PURPOSE_REGISTER = 'register'
    PURPOSE_CHOICES = (
        (PURPOSE_LOGIN, 'Login'),
        (PURPOSE_REGISTER, 'Register'),
    )

    phone = models.CharField(max_length=20, db_index=True)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    otp_hash = models.CharField(max_length=128)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'accounts'
        ordering = ['-created_at']

    @classmethod
    def create_code(cls, phone: str, purpose: str, ttl_minutes: int = 10) -> tuple['MobileOTP', str]:
        code = f'{random.randint(0, 999999):06d}'
        otp = cls.objects.create(
            phone=phone,
            purpose=purpose,
            otp_hash=make_password(code),
            expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
        )
        return otp, code

    def matches(self, code: str) -> bool:
        return check_password(code, self.otp_hash)

    @property
    def is_valid(self) -> bool:
        return not self.is_used and timezone.now() <= self.expires_at
