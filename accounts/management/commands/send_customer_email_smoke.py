from django.core.management.base import BaseCommand, CommandError

from accounts.services.email_service import EmailService


class Command(BaseCommand):
    help = "Send a customer email template to verify SMTP configuration."

    def add_arguments(self, parser):
        parser.add_argument("recipient")
        parser.add_argument(
            "--template",
            default="otp_login",
            choices=["otp_login", "welcome_customer", "order_placed", "invoice", "tax_invoice", "payment_failed", "order_cancelled"],
        )

    def handle(self, *args, **options):
        recipient = options["recipient"]
        template = options["template"]
        payload = {
            "customer_name": "Customer",
            "otp": "000000",
            "expiry_minutes": 10,
            "order_number": "SMOKE-ORDER",
            "store_name": "Smoke Test Store",
            "total": "100.00",
            "tax_amount": "5.00",
            "invoice_number": "SMOKE-INVOICE",
            "delivery_address": "Smoke test address",
            "message": "This is a smoke test email.",
        }
        try:
            EmailService.send_order_email(template, recipient, payload) if template != "otp_login" else EmailService.send_customer_login_otp(recipient, payload["otp"])
        except Exception as exc:
            raise CommandError(f"Email smoke test failed: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"Email smoke test sent to {recipient} using {template}."))
