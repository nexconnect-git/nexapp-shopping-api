"""Jinja renderer for reusable HTML email templates."""

from datetime import datetime
from pathlib import Path
from typing import Any

from django.conf import settings
from jinja2 import Environment, FileSystemLoader, select_autoescape


class EmailTemplateService:
    """Render Nextou email templates with shared safe defaults."""

    TEMPLATE_DIR = Path(settings.BASE_DIR).parent / "templates" / "emails"
    LEGAL_NOTE = "This is an automated email. Please do not reply directly to this message."
    _environment: Environment | None = None

    @classmethod
    def _env(cls) -> Environment:
        if cls._environment is None:
            cls._environment = Environment(
                loader=FileSystemLoader(str(cls.TEMPLATE_DIR)),
                autoescape=select_autoescape(["html", "html.j2", "j2", "xml"]),
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return cls._environment

    @staticmethod
    def _setting(name: str, default: str = "") -> str:
        value = getattr(settings, name, default)
        if value is None:
            return default
        return str(value)

    @classmethod
    def _shared_context(cls) -> dict[str, Any]:
        return {
            "brand_name": cls._setting("BRAND_NAME", "Nextou"),
            "brand_tagline": cls._setting("BRAND_TAGLINE", "Fast. Fresh. Delivered. \u26a1"),
            "current_year": datetime.now().year,
            "support_phone": cls._setting("SUPPORT_PHONE", "+91 80 1234 5678"),
            "support_email": cls._setting("SUPPORT_EMAIL", "support@nextou.in"),
            "support_hours": cls._setting("SUPPORT_HOURS", "Mon - Sun: 7AM - 11PM"),
            "help_url": cls._setting("HELP_URL", "#"),
            "faq_url": cls._setting("FAQ_URL", "#"),
            "support_url": cls._setting("SUPPORT_URL", "#"),
            "legal_note": cls._setting("EMAIL_LEGAL_NOTE", cls.LEGAL_NOTE),
        }

    @classmethod
    def render(cls, template_name: str, context: dict[str, Any] | None = None) -> str:
        payload = cls._shared_context()
        payload.update({key: value for key, value in (context or {}).items() if value is not None})
        return cls._env().get_template(template_name).render(**payload)

    @classmethod
    def render_customer_welcome(cls, context: dict[str, Any] | None = None) -> str:
        return cls.render("customer_welcome.html.j2", context)

    @classmethod
    def render_vendor_welcome(cls, context: dict[str, Any] | None = None) -> str:
        return cls.render("vendor_welcome.html.j2", context)

    @classmethod
    def render_vendor_approved(cls, context: dict[str, Any] | None = None) -> str:
        return cls.render("vendor_approved.html.j2", context)

    @classmethod
    def render_otp(cls, context: dict[str, Any] | None = None) -> str:
        return cls.render("otp_email.html.j2", context)

    @classmethod
    def render_admin_vendor_self_register_alert(cls, context: dict[str, Any] | None = None) -> str:
        return cls.render("admin_vendor_self_register_alert.html.j2", context)
