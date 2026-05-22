"""EmailService - email sending logic for customer-facing emails."""

import logging

from django.conf import settings
from django.core.mail import EmailMessage

from accounts.email_templates import render_customer_email

FRONTEND_URL = getattr(settings, "FRONTEND_URL", "https://nex-connect.in")
logger = logging.getLogger(__name__)


class EmailService:
    """Stateless service for sending account and customer lifecycle emails."""

    @staticmethod
    def _from_email() -> str:
        email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@nex-connect.in")
        name = getattr(settings, "DEFAULT_FROM_NAME", "")
        return f"{name} <{email}>" if name else email

    @staticmethod
    def _send(subject: str, message: str, recipient: str, *, log_context: str) -> None:
        if not recipient:
            logger.warning("Email skipped for %s because recipient is missing.", log_context)
            return
        try:
            EmailMessage(
                subject=subject,
                body=message,
                from_email=EmailService._from_email(),
                to=[recipient],
            ).send(fail_silently=False)
            logger.info("Email sent for %s to %s.", log_context, recipient)
        except Exception:
            logger.exception("Email send failed for %s to %s.", log_context, recipient)
            raise

    @staticmethod
    def _send_template(template_type: str, recipient: str, payload: dict, *, log_context: str) -> None:
        subject, message = render_customer_email(template_type, payload)
        EmailService._send(subject, message, recipient, log_context=log_context)

    @staticmethod
    def send_welcome_email(user) -> None:
        EmailService._send_template(
            "welcome_customer",
            user.email,
            {"customer_name": user.first_name or user.username},
            log_context=f"welcome customer {user.pk}",
        )

    @staticmethod
    def send_password_changed_email(user) -> None:
        EmailService._send(
            "Your NexConnect password has been changed",
            (
                f"Hi {user.first_name or user.username},\n\n"
                "Your password was recently changed. If you did not make this "
                "change, please contact support immediately."
            ),
            user.email,
            log_context=f"password changed user {user.pk}",
        )

    @staticmethod
    def send_password_reset_email(user, token: str) -> None:
        reset_url = f"{FRONTEND_URL}/reset-password?token={token}"
        EmailService._send(
            "Reset your NexConnect password",
            (
                f"Hi {user.first_name or user.username},\n\n"
                "We received a request to reset your password.\n\n"
                f"Click the link below to set a new password (valid for 1 hour):\n{reset_url}\n\n"
                "If you did not request this, you can safely ignore this email."
            ),
            user.email,
            log_context=f"password reset user {user.pk}",
        )

    @staticmethod
    def send_verification_email(user, otp: str) -> None:
        EmailService._send(
            "Verify your NexConnect email",
            (
                f"Hi {user.first_name or user.username},\n\n"
                f"Your email verification code is: {otp}\n\n"
                "This code expires in 15 minutes.\n\n"
                "If you did not request this, please ignore this email."
            ),
            user.email,
            log_context=f"verification user {user.pk}",
        )

    @staticmethod
    def send_customer_login_otp(email: str, otp: str, purpose: str = "login") -> None:
        EmailService._send_template(
            "otp_login",
            email,
            {"customer_name": "Customer", "otp": otp, "expiry_minutes": 10, "purpose": purpose},
            log_context=f"customer {purpose} OTP",
        )

    @staticmethod
    def send_order_email(template_type: str, recipient: str, payload: dict) -> None:
        EmailService._send_template(
            template_type,
            recipient,
            payload,
            log_context=f"order email {template_type}",
        )
