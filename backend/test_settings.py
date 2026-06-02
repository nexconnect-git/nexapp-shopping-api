import sys
from unittest.mock import MagicMock

sys.modules.setdefault("rq", MagicMock())
sys.modules.setdefault("django_rq", MagicMock())
sys.modules.setdefault("django_rq.queues", MagicMock())
sys.modules.setdefault("django_rq.jobs", MagicMock())
sys.modules.setdefault("django_rq.management", MagicMock())

from backend.settings import *  # noqa: F401,F403

DEBUG = True
SECRET_KEY = "test-only-insecure-secret-key"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
ROOT_URLCONF = "backend.test_urls"

INSTALLED_APPS = [
    app
    for app in INSTALLED_APPS
    if app
    not in {
        "daphne",
        "django.contrib.staticfiles",
        "django_rq",
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
MEDIA_ROOT = BASE_DIR / "test_media"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}
RQ_QUEUES = {}
