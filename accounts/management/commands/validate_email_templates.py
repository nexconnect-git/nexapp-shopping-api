import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from accounts.services.email_template_service import EmailTemplateService


class Command(BaseCommand):
    help = "Render Nextou email templates and verify no Jinja placeholders remain."

    TEMPLATE_RENDERERS = {
        "customer_welcome": EmailTemplateService.render_customer_welcome,
        "vendor_welcome": EmailTemplateService.render_vendor_welcome,
        "vendor_approved": EmailTemplateService.render_vendor_approved,
        "otp_email": EmailTemplateService.render_otp,
        "admin_vendor_self_register_alert": EmailTemplateService.render_admin_vendor_self_register_alert,
    }
    EXPECTED_VALUES = {
        "customer_welcome": "NEXTOU25",
        "vendor_welcome": "Fresh Basket Mart",
        "vendor_approved": "Fresh Basket Mart",
        "otp_email": "482614",
        "admin_vendor_self_register_alert": "owner@freshbasket.in",
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--sample-payloads",
            default=str(EmailTemplateService.TEMPLATE_DIR / "sample_payloads.json"),
            help="Path to sample_payloads.json.",
        )

    def handle(self, *args, **options):
        payload_path = Path(options["sample_payloads"])
        if not payload_path.exists():
            raise CommandError(f"Sample payload file not found: {payload_path}")

        payloads = json.loads(payload_path.read_text(encoding="utf-8"))
        for template_key, render in self.TEMPLATE_RENDERERS.items():
            html = render(payloads.get(template_key, {}))
            self._assert_clean(template_key, html)
            self._assert_contains(template_key, html, self.EXPECTED_VALUES[template_key])

            fallback_html = render({})
            self._assert_clean(f"{template_key} fallback", fallback_html)

        self.stdout.write(self.style.SUCCESS("All Nextou email templates rendered cleanly."))

    def _assert_clean(self, template_key: str, html: str) -> None:
        unresolved_tokens = ["{{", "{%", "{#"]
        unresolved = [token for token in unresolved_tokens if token in html]
        if unresolved:
            raise CommandError(
                f"{template_key} rendered with unresolved template tokens: {', '.join(unresolved)}"
            )

    def _assert_contains(self, template_key: str, html: str, expected_value: str) -> None:
        if expected_value not in html:
            raise CommandError(f"{template_key} did not render expected value: {expected_value}")
