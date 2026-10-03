import hashlib
import secrets
from datetime import timedelta

from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from accounts.models import PasswordResetToken, User
from vendors.data.base import BaseRepository

class PasswordResetRepository(BaseRepository):
    def __init__(self):
        super().__init__(PasswordResetToken)

    @staticmethod
    def issue(user):
        raw = secrets.token_urlsafe(48)
        PasswordResetToken.objects.filter(user=user, used=False).update(used=True)
        record = PasswordResetToken.objects.create(user=user, token=hashlib.sha256(raw.encode()).hexdigest(), expires_at=timezone.now() + timedelta(hours=1))
        return record, raw

    @staticmethod
    def locked_token(raw):
        return PasswordResetToken.objects.select_for_update().select_related('user').filter(token=hashlib.sha256(raw.encode()).hexdigest(), used=False, expires_at__gt=timezone.now(), user__is_active=True).first()

    @staticmethod
    def locked_user(pk):
        return User.objects.select_for_update().filter(pk=pk).first()

    @staticmethod
    def invalidate_sessions(user):
        for token in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=token)

    @staticmethod
    def has_recent_request(user):
        return PasswordResetToken.objects.filter(user=user, created_at__gte=timezone.now()-timedelta(minutes=1)).exists()
