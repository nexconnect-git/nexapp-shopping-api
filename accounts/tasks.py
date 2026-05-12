import logging

from django.conf import settings
from django.core.mail import send_mail
from django_rq import job

logger = logging.getLogger(__name__)


@job('default')
def send_mobile_otp_email(email: str, otp_code: str, purpose: str) -> None:
    purpose_label = 'login' if purpose == 'login' else 'registration'
    try:
        send_mail(
            subject=f'Your NexConnect {purpose_label} OTP',
            message=(
                f'Your NexConnect {purpose_label} OTP is: {otp_code}\n\n'
                'This code expires in 10 minutes. If you did not request this, please ignore this email.'
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@nex-connect.in'),
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.error('Failed to send mobile OTP fallback email to %s: %s', email, exc)
