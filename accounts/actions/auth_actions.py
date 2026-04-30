"""Auth actions — orchestrate registration, login, mobile OTP auth, and email verification."""

import re
import uuid
from django.contrib.auth import authenticate
from django.conf import settings

from accounts.data.user_repository import UserRepository
from accounts.helpers.token_helpers import generate_tokens_for_user
from accounts.models.email_verification import EmailVerification
from accounts.models.mobile_otp import MobileOTP
from accounts.serializers.user_serializers import (
    MobileOTPRequestSerializer,
    MobileOTPVerifySerializer,
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
        if self._data.get('role', 'customer') == 'customer':
            raise ValueError('Customer accounts must be created with mobile OTP.')

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
        if user.role == 'customer':
            raise ValueError('Customers must sign in with mobile OTP.')

        tokens = generate_tokens_for_user(user)
        return {
            'user': UserProfileSerializer(user).data,
            'tokens': tokens,
        }


def normalize_phone(phone: str) -> str:
    normalized = re.sub(r'[^\d+]', '', (phone or '').strip())
    if not normalized:
        raise ValueError('Mobile number is required.')
    return normalized


def _build_customer_username(phone: str) -> str:
    suffix = re.sub(r'\D', '', phone)[-6:] or 'user'
    return f'cust_{suffix}_{uuid.uuid4().hex[:6]}'


class RequestMobileOTPAction:
    def __init__(self, data: dict, purpose: str):
        self._data = data
        self._purpose = purpose

    def execute(self) -> dict:
        serializer = MobileOTPRequestSerializer(data=self._data)
        serializer.is_valid(raise_exception=True)
        phone = normalize_phone(serializer.validated_data['phone'])
        customer = UserRepository.get_by_phone(phone, role='customer')

        if self._purpose == MobileOTP.PURPOSE_LOGIN and customer is None:
            raise ValueError('No customer account found for this mobile number. Please create an account first.')

        if self._purpose == MobileOTP.PURPOSE_REGISTER and customer is not None:
            raise ValueError('An account already exists for this mobile number. Please sign in instead.')

        _otp, code = MobileOTP.create_code(phone=phone, purpose=self._purpose)
        payload = {'detail': 'OTP sent successfully.', 'phone': phone}
        if customer is not None:
            payload['user_exists'] = True
        if self._purpose == MobileOTP.PURPOSE_REGISTER:
            payload['user_exists'] = False
        if settings.DEBUG:
            payload['dev_otp'] = code
        return payload


class VerifyMobileOTPAction:
    def __init__(self, data: dict, purpose: str):
        self._data = data
        self._purpose = purpose

    def execute(self) -> dict:
        serializer = MobileOTPVerifySerializer(data=self._data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        phone = normalize_phone(payload['phone'])
        otp_code = payload['otp']

        otp = (
            MobileOTP.objects
            .filter(phone=phone, purpose=self._purpose, is_used=False)
            .order_by('-created_at')
            .first()
        )
        if not otp or not otp.is_valid or not otp.matches(otp_code):
            raise ValueError('Invalid or expired OTP.')

        otp.is_used = True
        otp.save(update_fields=['is_used'])

        user = UserRepository.get_by_phone(phone, role='customer')
        if self._purpose == MobileOTP.PURPOSE_LOGIN:
            if user is None:
                raise ValueError('No customer account found for this mobile number.')
        else:
            if user is not None:
                raise ValueError('An account already exists for this mobile number.')

            first_name = payload.get('first_name', '').strip()
            if not first_name:
                raise ValueError('First name is required to create an account.')

            user = UserProfileSerializer.Meta.model.objects.create(
                username=_build_customer_username(phone),
                first_name=first_name,
                last_name=payload.get('last_name', '').strip(),
                email=payload.get('email', '').strip(),
                phone=phone,
                role='customer',
            )
            user.set_unusable_password()
            user.save()

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
