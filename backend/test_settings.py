"""
Test settings for Windows development.

Replaces django_rq with a no-op stub so the test runner can boot on Windows
where rq's scheduler tries to use multiprocessing 'fork' (unsupported on Windows).
"""
import sys
from unittest.mock import MagicMock

# Stub out rq / django_rq before Django tries to import them.
# This must happen before settings are fully loaded.
sys.modules.setdefault("rq", MagicMock())
sys.modules.setdefault("django_rq", MagicMock())

from backend.settings import *  # noqa: F401, F403

# Remove daphne (ASGI server — not needed for tests) and django_rq from apps.
INSTALLED_APPS = [
    app for app in INSTALLED_APPS
    if app not in ("daphne", "django_rq")
]

# Use a fast in-memory password hasher for tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Use in-process SQLite for speed.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Silence channels/redis config warnings during tests.
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# Suppress URL system checks — optional packages (rq_scheduler, xhtml2pdf, etc.)
# are not installed in the dev venv but are only needed in production URL routes
# that we aren't exercising in these tests.
SILENCED_SYSTEM_CHECKS = ["urls.W005", "urls.E007", "urls.W001"]

# Skip URL traversal during system checks (avoids importing optional packages).
ROOT_URLCONF = "backend.test_urls"

# Use in-memory dummy cache so tests don't require a live Redis server.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}
