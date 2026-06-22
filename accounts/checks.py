from django.conf import settings
from django.core.checks import Error, Warning, register


@register()
def email_configuration_check(app_configs, **kwargs):
    issues = []
    backend = str(getattr(settings, 'EMAIL_BACKEND', '') or '')
    non_sending_backends = (
        'console.EmailBackend',
        'dummy.EmailBackend',
        'locmem.EmailBackend',
        'filebased.EmailBackend',
    )

    if not settings.DEBUG and any(name in backend for name in non_sending_backends):
        issues.append(
            Error(
                'Production email is configured with a non-sending backend.',
                hint=(
                    'Set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend '
                    'and provide EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, '
                    'EMAIL_HOST_PASSWORD, and EMAIL_USE_TLS/EMAIL_USE_SSL.'
                ),
                id='accounts.E001',
            )
        )

    if not settings.DEBUG and 'smtp.EmailBackend' in backend:
        if not getattr(settings, 'EMAIL_HOST', '') or settings.EMAIL_HOST == 'localhost':
            issues.append(
                Error(
                    'Production SMTP email is missing EMAIL_HOST.',
                    hint='Set EMAIL_HOST or SMTP_HOST to your SMTP provider host.',
                    id='accounts.E002',
                )
            )
        if not getattr(settings, 'DEFAULT_FROM_EMAIL', ''):
            issues.append(
                Error(
                    'Production SMTP email is missing DEFAULT_FROM_EMAIL.',
                    hint='Set DEFAULT_FROM_EMAIL or EMAIL_FROM_ADDRESS.',
                    id='accounts.E003',
                )
            )
        if not getattr(settings, 'EMAIL_HOST_USER', ''):
            issues.append(
                Warning(
                    'SMTP email has no username configured.',
                    hint='If your provider requires authentication, set EMAIL_HOST_USER or SMTP_EMAIL.',
                    id='accounts.W001',
                )
            )
        if not getattr(settings, 'EMAIL_HOST_PASSWORD', ''):
            issues.append(
                Warning(
                    'SMTP email has no password/API key configured.',
                    hint='If your provider requires authentication, set EMAIL_HOST_PASSWORD or SMTP_APP_PASSWORD.',
                    id='accounts.W002',
                )
            )

    return issues
