"""Local Windows-friendly settings for one-off SQLite smoke checks."""

import sys
from unittest.mock import MagicMock

sys.modules.setdefault("rq", MagicMock())
sys.modules.setdefault("django_rq", MagicMock())

from backend.settings import *  # noqa: F401, F403

INSTALLED_APPS = [
    app for app in INSTALLED_APPS
    if app not in ("daphne", "django_rq")
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DB_NAME", "db.sqlite3"),
    }
}

CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
ROOT_URLCONF = "backend.test_urls"
SILENCED_SYSTEM_CHECKS = ["urls.W005", "urls.E007", "urls.W001"]
ALLOWED_HOSTS = [*ALLOWED_HOSTS, "testserver"]
