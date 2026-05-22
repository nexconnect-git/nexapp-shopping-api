"""Auth actions — orchestrate registration, login, mobile OTP auth, and email verification."""

import logging
import uuid
import django_rq
from django.contrib.auth import authenticate
from django.conf import settings
from django.utils import timezone

from accounts.data.user_repository import UserRepository
from accounts.helpers.token_helpers import generate_tokens_for_user
from accounts.models.email_verification import EmailVerification
from accounts.models.mobile_otp import MobileOTP
from accounts.serializers.user_serializers import (
    AdminUserSerializer,
    MobileOTPRequestSerializer,
    MobileOTPVerifySerializer,
    UserRegistrationSerializer,
    UserProfileSerializer,
)
from accounts.services.email_service import EmailService
from accounts.tasks import send_mobile_otp_email
from helpers.phone_helpers import normalize_phone

logger = logging.getLogger(__name__)
OTP_RESEND_COOLDOWN_SECONDS = 60


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
                logger.exception('Email verification send failed for user %s.', user.id)

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


class SetupSuperUserAction:
    """Create the first superuser when the system has no superuser account."""

    def __init__(self, data: dict):
        self._data = data

    def execute(self) -> dict:
        if UserRepository.superuser_exists():
            raise ValueError('A superuser already exists in the system.')

        data = self._data.copy()
        data['account_type'] = 'superuser'

        serializer = AdminUserSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return UserProfileSerializer(user).data


def _build_customer_username(phone: str) -> str:
    suffix = ''.join(char for char in phone if char.isdigit())[-6:] or 'user'
    return f'cust_{suffix}_{uuid.uuid4().hex[:6]}'


class RequestMobileOTPAction:
    def __init__(self, data: dict, purpose: str):
        self._data = data
        self._purpose = purpose

    def execute(self) -> dict:
        serializer = MobileOTPRequestSerializer(data=self._data)
        serializer.is_valid(raise_exception=True)
        phone = normalize_phone(serializer.validated_data['phone'])
        fallback_email = serializer.validated_data.get('email', '').strip().lower()
        if not fallback_email:
            raise ValueError('Email is required to send your OTP.')
        customer = UserRepository.get_by_phone(phone, role='customer')

        email_for_otp = fallback_email
        if self._purpose == MobileOTP.PURPOSE_LOGIN:
            if customer is not None:
                registered_email = (customer.email or '').strip().lower()
                if not registered_email:
                    raise ValueError('This account does not have an email address for OTP login. Please contact support.')
                if registered_email != fallback_email:
                    raise ValueError('Enter the email address linked to this mobile number.')
            else:
                if UserRepository.phone_exists(phone):
                    raise ValueError('This mobile number is already registered for another account type.')
                if UserRepository.email_exists(fallback_email):
                    raise ValueError('An account already exists for this email address. Please sign in with the registered mobile number.')

        if self._purpose == MobileOTP.PURPOSE_REGISTER and UserRepository.phone_exists(phone):
            raise ValueError('An account already exists for this mobile number. Please sign in instead.')
        if self._purpose == MobileOTP.PURPOSE_REGISTER and UserRepository.email_exists(fallback_email):
            raise ValueError('An account already exists for this email address. Please sign in instead.')
        if self._purpose == MobileOTP.PURPOSE_REGISTER:
            email_for_otp = fallback_email

        latest = (
            MobileOTP.objects
            .filter(phone=phone, purpose=self._purpose, email=email_for_otp, is_used=False)
            .order_by('-created_at')
            .first()
        )
        if latest and latest.created_at > timezone.now() - timezone.timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS):
            raise ValueError('Please wait before requesting another OTP.')

        _otp, code = MobileOTP.create_code(phone=phone, purpose=self._purpose, email=email_for_otp)
        email_queued = self._queue_email_fallback(code, email_for_otp)
        payload = {'detail': 'OTP sent successfully.', 'phone': phone}
        if email_queued:
            payload['email_fallback_queued'] = True
        if self._purpose == MobileOTP.PURPOSE_LOGIN:
            payload['user_exists'] = customer is not None
        if self._purpose == MobileOTP.PURPOSE_REGISTER:
            payload['user_exists'] = False
        if settings.DEBUG and getattr(settings, 'CUSTOMER_AUTH_EXPOSE_DEV_OTP', False):
            payload['dev_otp'] = code
        return payload

    def _queue_email_fallback(self, code: str, email: str) -> bool:
        if not email:
            return False

        try:
            queue = django_rq.get_queue('default')
            queue.enqueue(send_mobile_otp_email, email, code, self._purpose)
            return True
        except Exception:
            logger.exception('Could not enqueue customer OTP email for %s; trying direct send.', email)
            try:
                EmailService.send_customer_login_otp(email, code, self._purpose)
                return False
            except Exception as exc:
                logger.exception('Customer OTP email failed for %s.', email)
                raise ValueError('Email service is temporarily unavailable. Please try again later.') from exc


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
        created_customer = False
        if self._purpose == MobileOTP.PURPOSE_LOGIN:
            if user is None:
                email = (otp.email or payload.get('email', '')).strip().lower()
                if not email:
                    raise ValueError('Email is required to create your account.')
                if UserRepository.email_exists(email):
                    raise ValueError('An account already exists for this email address. Please sign in with the registered mobile number.')
                user = UserProfileSerializer.Meta.model.objects.create(
                    username=_build_customer_username(phone),
                    email=email,
                    phone=phone,
                    role='customer',
                )
                user.set_unusable_password()
                user.save()
                created_customer = True
        else:
            if UserRepository.phone_exists(phone):
                raise ValueError('An account already exists for this mobile number.')

            first_name = payload.get('first_name', '').strip()
            if not first_name:
                raise ValueError('First name is required to create an account.')

            email = (payload.get('email', '') or otp.email).strip().lower()
            if UserRepository.email_exists(email):
                raise ValueError('An account already exists for this email address.')

            user = UserProfileSerializer.Meta.model.objects.create(
                username=_build_customer_username(phone),
                first_name=first_name,
                last_name=payload.get('last_name', '').strip(),
                email=email,
                phone=phone,
                role='customer',
            )
            user.set_unusable_password()
            user.save()
            created_customer = True

        if created_customer and user.email:
            try:
                EmailService.send_welcome_email(user)
            except Exception:
                logger.exception('Welcome email send failed for customer %s.', user.id)

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
