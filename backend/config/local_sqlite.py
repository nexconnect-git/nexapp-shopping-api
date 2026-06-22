"""Local Windows-friendly settings for one-off SQLite smoke checks."""

import sys
import os
from unittest.mock import MagicMock

sys.modules.setdefault("rq", MagicMock())
sys.modules.setdefault("django_rq", MagicMock())
os.environ.setdefault("SECRET_KEY", "local-sqlite-smoke-check-secret-key")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

from backend.config.settings import *  # noqa: F401, F403

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
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
ROOT_URLCONF = "backend.routes"
SILENCED_SYSTEM_CHECKS = ["urls.W005", "urls.E007", "urls.W001", "accounts.E001"]
ALLOWED_HOSTS = [*ALLOWED_HOSTS, "testserver"]
DEBUG = False
ENABLE_DJANGO_RQ_DASHBOARD = False
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_PROXY_SSL_HEADER = None
