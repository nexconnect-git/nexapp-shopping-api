"""EmailService - email sending logic for account and lifecycle emails."""

import logging
import re
from collections.abc import Iterable

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags

from accounts.email_templates import render_customer_email
from accounts.services.email_template_service import EmailTemplateService

FRONTEND_URL = getattr(settings, "FRONTEND_URL", "https://nex-connect.in")
logger = logging.getLogger(__name__)


class EmailService:
    """Stateless service for sending account and lifecycle emails."""

    @staticmethod
    def _from_email() -> str:
        email = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@nextou.in")
        name = getattr(settings, "DEFAULT_FROM_NAME", "")
        return f"{name} <{email}>" if name else email

    @staticmethod
    def _brand_name() -> str:
        return str(getattr(settings, "BRAND_NAME", "Nextou") or "Nextou")

    @staticmethod
    def _setting(name: str, default: str = "") -> str:
        value = getattr(settings, name, default)
        if value is None:
            return default
        return str(value).strip()

    @staticmethod
    def _join_url(base: str, path: str = "") -> str:
        base = (base or "").strip()
        if not base:
            return "#"
        if not path:
            return base
        return f"{base.rstrip('/')}/{path.lstrip('/')}"

    @staticmethod
    def _customer_app_url(path: str = "") -> str:
        base = EmailService._setting("CUSTOMER_APP_URL") or FRONTEND_URL
        return EmailService._join_url(base, path)

    @staticmethod
    def _vendor_app_url(path: str = "") -> str:
        base = EmailService._setting("VENDOR_APP_URL") or EmailService._customer_app_url()
        return EmailService._join_url(base, path)

    @staticmethod
    def _admin_panel_url(path: str = "") -> str:
        base = EmailService._setting("ADMIN_PANEL_URL") or EmailService._customer_app_url()
        return EmailService._join_url(base, path)

    @staticmethod
    def _html_to_text(html: str) -> str:
        text = strip_tags(html)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()

    @staticmethod
    def _recipient_email(target) -> str:
        if isinstance(target, str):
            return target.strip()
        if isinstance(target, dict):
            return str(target.get("email") or "").strip()
        return str(getattr(target, "email", "") or "").strip()

    @staticmethod
    def _display_name(user, fallback: str = "Customer") -> str:
        first_name = str(getattr(user, "first_name", "") or "").strip()
        last_name = str(getattr(user, "last_name", "") or "").strip()
        full_name = " ".join(part for part in [first_name, last_name] if part)
        return full_name or str(getattr(user, "username", "") or getattr(user, "email", "") or fallback)

    @staticmethod
    def _vendor_display_name(vendor) -> str:
        user = getattr(vendor, "user", None)
        return EmailService._display_name(user, fallback=getattr(vendor, "store_name", "Vendor"))

    @staticmethod
    def _parse_recipients(value) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            parts = re.split(r"[,;]", value)
        elif isinstance(value, Iterable):
            parts = value
        else:
            parts = [value]
        return [str(part).strip() for part in parts if str(part).strip()]

    @staticmethod
    def _admin_vendor_review_recipients() -> list[str]:
        return EmailService._parse_recipients(
            getattr(settings, "ADMIN_VENDOR_REVIEW_EMAIL", "")
            or getattr(settings, "ADMIN_VENDOR_REVIEW_EMAILS", "")
        )

    @staticmethod
    def _send(
        subject: str,
        message: str,
        recipient: str,
        *,
        log_context: str,
        html_message: str | None = None,
    ) -> None:
        EmailService._send_many(
            subject,
            message,
            [recipient],
            log_context=log_context,
            html_message=html_message,
        )

    @staticmethod
    def _send_many(
        subject: str,
        message: str,
        recipients: Iterable[str],
        *,
        log_context: str,
        html_message: str | None = None,
    ) -> None:
        to = EmailService._parse_recipients(recipients)
        if not to:
            logger.warning("Email skipped for %s because recipient is missing.", log_context)
            return
        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=message,
                from_email=EmailService._from_email(),
                to=to,
            )
            if html_message:
                email.attach_alternative(html_message, "text/html")
            email.send(fail_silently=False)
            logger.info("Email sent for %s to %s.", log_context, ", ".join(to))
        except Exception:
            logger.exception("Email send failed for %s to %s.", log_context, ", ".join(to))
            raise

    @staticmethod
    def _send_template(template_type: str, recipient: str, payload: dict, *, log_context: str) -> None:
        subject, message = render_customer_email(template_type, payload)
        EmailService._send(subject, message, recipient, log_context=log_context)

    @staticmethod
    def _send_html_template(
        *,
        template_name: str,
        subject: str,
        recipients: Iterable[str],
        context: dict,
        text_fallback: str,
        log_context: str,
    ) -> None:
        html = EmailTemplateService.render(template_name, {"subject": subject, **context})
        plain_text = text_fallback.strip() or EmailService._html_to_text(html)
        EmailService._send_many(
            subject,
            plain_text,
            recipients,
            log_context=log_context,
            html_message=html,
        )

    @staticmethod
    def send_customer_welcome_email(customer) -> None:
        customer_name = EmailService._display_name(customer)
        subject = "Welcome to Nextou"
        start_shopping_url = EmailService._customer_app_url()
        context = {
            "user_name": customer_name,
            "customer_name": customer_name,
            "start_shopping_url": start_shopping_url,
            "coupon_code": EmailService._setting("WELCOME_COUPON_CODE", "NEXTOU25") or "NEXTOU25",
            "coupon_note": EmailService._setting("WELCOME_COUPON_NOTE", "Valid for a limited time."),
            "delivery_time": EmailService._setting("WELCOME_DELIVERY_TIME", "20 mins"),
        }
        EmailService._send_html_template(
            template_name="customer_welcome.html.j2",
            subject=subject,
            recipients=[customer.email],
            context=context,
            text_fallback=(
                f"Hi {customer_name}, welcome to {EmailService._brand_name()}. "
                f"Start shopping here: {start_shopping_url}"
            ),
            log_context=f"welcome customer {customer.pk}",
        )

    @staticmethod
    def send_welcome_email(user) -> None:
        EmailService.send_customer_welcome_email(user)

    @staticmethod
    def send_vendor_welcome_email(vendor) -> None:
        vendor_name = EmailService._vendor_display_name(vendor)
        store_name = getattr(vendor, "store_name", "") or vendor_name
        complete_setup_url = EmailService._vendor_app_url("store-settings")
        partner_support_url = EmailService._vendor_app_url("support")
        subject = "Welcome to Nextou Partner Hub"
        context = {
            "vendor_name": vendor_name,
            "store_name": store_name,
            "complete_setup_url": complete_setup_url,
            "partner_support_url": partner_support_url,
        }
        EmailService._send_html_template(
            template_name="vendor_welcome.html.j2",
            subject=subject,
            recipients=[getattr(vendor, "email", "") or getattr(vendor.user, "email", "")],
            context=context,
            text_fallback=(
                f"Hi {vendor_name}, welcome to {EmailService._brand_name()} Partner Hub. "
                f"Complete your store setup here: {complete_setup_url}"
            ),
            log_context=f"vendor welcome {vendor.pk}",
        )

    @staticmethod
    def send_vendor_approved_email(vendor) -> None:
        vendor_name = EmailService._vendor_display_name(vendor)
        dashboard_url = EmailService._vendor_app_url()
        subject = "Your Nextou vendor account is approved"
        context = {
            "vendor_name": vendor_name,
            "store_name": getattr(vendor, "store_name", "") or vendor_name,
            "dashboard_url": dashboard_url,
        }
        EmailService._send_html_template(
            template_name="vendor_approved.html.j2",
            subject=subject,
            recipients=[getattr(vendor, "email", "") or getattr(vendor.user, "email", "")],
            context=context,
            text_fallback=(
                f"Congratulations {vendor_name}, your {EmailService._brand_name()} vendor account "
                f"is approved. Open your dashboard: {dashboard_url}"
            ),
            log_context=f"vendor approved {vendor.pk}",
        )

    @staticmethod
    def send_admin_vendor_self_register_alert(vendor) -> None:
        recipients = EmailService._admin_vendor_review_recipients()
        review_application_url = EmailService._admin_panel_url(f"vendors/{vendor.pk}/review")
        admin_panel_url = EmailService._admin_panel_url()
        vendor_category = (
            vendor.get_vendor_type_display()
            if hasattr(vendor, "get_vendor_type_display")
            else getattr(vendor, "vendor_type", "")
        )
        context = {
            "vendor_name": EmailService._vendor_display_name(vendor),
            "store_name": getattr(vendor, "store_name", ""),
            "vendor_phone": getattr(vendor, "phone", ""),
            "vendor_email": getattr(vendor, "email", "") or getattr(vendor.user, "email", ""),
            "vendor_city": getattr(vendor, "city", ""),
            "vendor_category": vendor_category,
            "review_status": "Pending Review",
            "review_application_url": review_application_url,
            "admin_panel_url": admin_panel_url,
        }
        EmailService._send_html_template(
            template_name="admin_vendor_self_register_alert.html.j2",
            subject="New vendor registration received",
            recipients=recipients,
            context=context,
            text_fallback=(
                f"New vendor registration received for {context['store_name'] or context['vendor_name']}. "
                f"Review it here: {review_application_url}"
            ),
            log_context=f"admin vendor self-register alert {vendor.pk}",
        )

    @staticmethod
    def _otp_subject(purpose: str) -> str:
        purpose_key = (purpose or "").strip().lower().replace("_", " ")
        if "login" in purpose_key:
            return "Verify your Nextou login"
        if "password" in purpose_key or "reset" in purpose_key:
            return "Reset your Nextou password"
        return "Your Nextou OTP"

    @staticmethod
    def send_otp_email(target, otp: str, purpose: str = "login", expiry_minutes: int | None = None) -> None:
        recipient = EmailService._recipient_email(target)
        purpose_label = (purpose or "login").strip().replace("_", " ")
        purpose_display = purpose_label[:1].upper() + purpose_label[1:]
        expiry = int(expiry_minutes or getattr(settings, "OTP_EXPIRY_MINUTES", 10) or 10)
        subject = EmailService._otp_subject(purpose_label)
        app_url = EmailService._customer_app_url()
        context = {
            "otp_code": otp,
            "app_url": app_url,
            "purpose": purpose_display,
            "expiry_minutes": expiry,
            "preheader": f"Use this code within {expiry} minutes.",
            "security_notes": [
                {
                    "icon": "\u23f1\ufe0f",
                    "title": f"Valid for {expiry} minutes",
                    "text": f"This code will expire in {expiry} minutes.",
                },
                {
                    "icon": "\U0001f6e1\ufe0f",
                    "title": "Do not share this code",
                    "text": "For your security, never share this OTP with anyone.",
                },
                {
                    "icon": "\u2709\ufe0f",
                    "title": "If you did not request this",
                    "text": "You can safely ignore this email.",
                },
            ],
        }
        EmailService._send_html_template(
            template_name="otp_email.html.j2",
            subject=subject,
            recipients=[recipient],
            context=context,
            text_fallback=(
                f"Your {EmailService._brand_name()} OTP is {otp}. "
                f"It expires in {expiry} minutes. Do not share this code."
            ),
            log_context=f"OTP {purpose_label} email",
        )

    @staticmethod
    def send_password_changed_email(user) -> None:
        EmailService._send(
            "Your Nextou password has been changed",
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
            "Reset your Nextou password",
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
        EmailService.send_otp_email(
            user,
            otp,
            purpose="email verification",
            expiry_minutes=int(getattr(settings, "EMAIL_VERIFICATION_EXPIRY_MINUTES", 15) or 15),
        )

    @staticmethod
    def send_customer_login_otp(email: str, otp: str, purpose: str = "login") -> None:
        EmailService.send_otp_email(
            email,
            otp,
            purpose=purpose,
            expiry_minutes=int(getattr(settings, "OTP_EXPIRY_MINUTES", 10) or 10),
        )

    @staticmethod
    def send_order_email(template_type: str, recipient: str, payload: dict) -> None:
        EmailService._send_template(
            template_type,
            recipient,
            payload,
            log_context=f"order email {template_type}",
        )
