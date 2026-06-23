"""Canonical test settings for documented backend customer-flow tests."""

from backend.config.local_sqlite import *  # noqa: F401, F403

DATABASES["default"]["NAME"] = ":memory:"  # noqa: F405
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
