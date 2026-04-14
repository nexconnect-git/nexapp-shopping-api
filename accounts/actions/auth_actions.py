"""Auth actions — orchestrate registration, login, and email verification."""

from django.contrib.auth import authenticate

from accounts.helpers.token_helpers import generate_tokens_for_user
from accounts.models.email_verification import EmailVerification
from accounts.serializers.user_serializers import (
    UserRegistrationSerializer,
    UserProfileSerializer,
)
from accounts.services.email_service import EmailService


class RegisterAction:
    """Orchestrates new-user registration and sends an email verification OTP."""

    def __init__(self, data: dict):
        self._data = data

    def execute(self) -> dict:
        """Validate, create the user, send verification OTP, return profile + tokens.

        Returns:
            Dictionary with ``user`` profile data and ``tokens``.

        Raises:
            rest_framework.exceptions.ValidationError: on invalid input.
        """
        serializer = UserRegistrationSerializer(data=self._data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Send email verification OTP (fire-and-forget; failures don't block registration)
        if user.email:
            try:
                verification = EmailVerification.create_for_user(user)
                EmailService.send_verification_email(user, verification.otp)
            except Exception:
                pass  # Log would surface via Sentry; don't break registration

        tokens = generate_tokens_for_user(user)
        return {
            'user': UserProfileSerializer(user).data,
            'tokens': tokens,
        }


class LoginAction:
    """Orchestrates credential validation and token issuance."""

    def __init__(self, username: str, password: str):
        self._username = username
        self._password = password

    def execute(self) -> dict:
        """Authenticate the user and return profile + tokens.

        Returns:
            Dictionary with ``user`` profile data and ``tokens``.

        Raises:
            ValueError: If credentials are missing or invalid.
        """
        if not self._username or not self._password:
            raise ValueError('Username and password are required.')

        user = authenticate(username=self._username, password=self._password)
        if user is None:
            raise ValueError('Invalid credentials.')

        tokens = generate_tokens_for_user(user)
        return {
            'user': UserProfileSerializer(user).data,
            'tokens': tokens,
        }


class SendVerificationEmailAction:
    """Re-sends an email verification OTP to the requesting user."""

    def __init__(self, user):
        self._user = user

    def execute(self) -> None:
        """Create a fresh OTP and send it.

        Raises:
            ValueError: If the user's email is already verified.
        """
        if self._user.is_verified:
            raise ValueError('Email is already verified.')

        verification = EmailVerification.create_for_user(self._user)
        EmailService.send_verification_email(self._user, verification.otp)


class VerifyEmailAction:
    """Validates an OTP and marks the user's email as verified."""

    def __init__(self, user, otp: str):
        self._user = user
        self._otp = otp

    def execute(self) -> None:
        """Check the OTP and flip ``user.is_verified``.

        Raises:
            ValueError: If the OTP is invalid or expired.
        """
        if self._user.is_verified:
            raise ValueError('Email is already verified.')

        verification = (
            EmailVerification.objects
            .filter(user=self._user, otp=self._otp, is_used=False)
            .order_by('-created_at')
            .first()
        )

        if not verification or not verification.is_valid:
            raise ValueError('Invalid or expired OTP.')

        verification.is_used = True
        verification.save(update_fields=['is_used'])

        self._user.is_verified = True
        self._user.save(update_fields=['is_verified'])
