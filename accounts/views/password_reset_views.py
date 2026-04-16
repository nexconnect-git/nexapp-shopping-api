"""Token-based password reset views."""

import logging

from django.contrib.auth import get_user_model
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from accounts.models import PasswordResetToken
from accounts.services.email_service import EmailService

logger = logging.getLogger(__name__)
User = get_user_model()


class RequestPasswordResetView(APIView):
    """POST /api/auth/password-reset/

    Accepts ``{ "email": "..." }`` and sends a reset link if the address
    is registered.  Always returns 200 so callers cannot enumerate accounts.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        if email:
            try:
                user = User.objects.get(email__iexact=email, is_active=True)
                token_obj = PasswordResetToken.create_for_user(user)
                EmailService.send_password_reset_email(user, token_obj.token)
            except User.DoesNotExist:
                pass  # Silently ignore — no user enumeration
            except Exception as exc:
                logger.error("Password reset email failed for %s: %s", email, exc)

        return Response({'detail': 'If that email is registered, a reset link has been sent.'})


class ConfirmPasswordResetView(APIView):
    """POST /api/auth/password-reset/confirm/

    Accepts ``{ "token": "...", "new_password": "..." }``.
    Validates the token and sets the new password.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        token_str = (request.data.get('token') or '').strip()
        new_password = (request.data.get('new_password') or '').strip()

        if not token_str or not new_password:
            return Response(
                {'error': 'token and new_password are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(new_password) < 8:
            return Response(
                {'error': 'Password must be at least 8 characters.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token_obj = PasswordResetToken.objects.select_related('user').get(token=token_str)
        except PasswordResetToken.DoesNotExist:
            return Response({'error': 'Invalid or expired reset link.'}, status=status.HTTP_400_BAD_REQUEST)

        if not token_obj.is_valid:
            return Response({'error': 'This reset link has expired or already been used.'}, status=status.HTTP_400_BAD_REQUEST)

        user = token_obj.user
        user.set_password(new_password)
        user.save(update_fields=['password'])

        token_obj.used = True
        token_obj.save(update_fields=['used'])

        EmailService.send_password_changed_email(user)
        return Response({'detail': 'Password has been reset successfully.'})
