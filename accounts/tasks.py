import logging

from django_rq import job

from accounts.services.email_service import EmailService

logger = logging.getLogger(__name__)


@job('default')
def send_mobile_otp_email(email: str, otp_code: str, purpose: str) -> None:
    purpose_label = 'login' if purpose == 'login' else 'registration'
    try:
        EmailService.send_customer_login_otp(email, otp_code, purpose_label)
    except Exception as exc:
        logger.exception('Failed to send customer OTP email to %s for %s.', email, purpose_label)
        raise
