"""Vendor email actions."""

import logging

from accounts.services.email_service import EmailService
from vendors.actions.base import BaseAction

logger = logging.getLogger(__name__)


class SendVendorWelcomeEmailAction(BaseAction):
    """Send a non-blocking welcome email to a newly created vendor."""

    def execute(self, vendor) -> None:
        try:
            EmailService.send_vendor_welcome_email(vendor)
        except Exception:
            logger.exception("Vendor welcome email failed for vendor %s.", vendor.pk)


class SendVendorSelfRegistrationEmailsAction(BaseAction):
    """Send non-blocking emails for public vendor self-registration."""

    def execute(self, vendor) -> None:
        SendVendorWelcomeEmailAction().execute(vendor)

        try:
            EmailService.send_admin_vendor_self_register_alert(vendor)
        except Exception:
            logger.exception("Admin vendor self-register alert failed for vendor %s.", vendor.pk)
