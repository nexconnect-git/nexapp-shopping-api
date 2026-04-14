"""EmailService — email sending logic for the accounts app."""

from django.core.mail import send_mail
from django.conf import settings


class EmailService:
    """Stateless service for sending account-related emails."""

    @staticmethod
    def send_welcome_email(user) -> None:
        """Send a welcome email to a newly registered user."""
        send_mail(
            subject='Welcome to NexConnect',
            message=(
                f'Hi {user.first_name or user.username},\n\n'
                'Your account has been created successfully.\n\n'
                'Thank you for joining NexConnect!'
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@nexconnect.com'),
            recipient_list=[user.email],
            fail_silently=True,
        )

    @staticmethod
    def send_password_changed_email(user) -> None:
        """Notify a user that their password was changed."""
        send_mail(
            subject='Your NexConnect password has been changed',
            message=(
                f'Hi {user.first_name or user.username},\n\n'
                'Your password was recently changed. If you did not make this '
                'change, please contact support immediately.'
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@nexconnect.com'),
            recipient_list=[user.email],
            fail_silently=True,
        )

    @staticmethod
    def send_verification_email(user, otp: str) -> None:
        """Send a 6-digit OTP to the user's email address for verification.

        Args:
            user: The User instance to send to.
            otp: The 6-digit OTP string to include in the email.
        """
        send_mail(
            subject='Verify your NexConnect email',
            message=(
                f'Hi {user.first_name or user.username},\n\n'
                f'Your email verification code is: {otp}\n\n'
                'This code expires in 15 minutes.\n\n'
                'If you did not request this, please ignore this email.'
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@nexconnect.com'),
            recipient_list=[user.email],
            fail_silently=False,
        )
