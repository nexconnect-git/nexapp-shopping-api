import os
import sentry_sdk
from pathlib import Path
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs):
        return False

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR.parent / '.env')
load_dotenv(BASE_DIR / '.env')


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


DJANGO_ENV = os.environ.get('DJANGO_ENV', 'local').strip().lower()

DEBUG = env_bool('DEBUG', False)
PUBLIC_BACKEND_URL = os.environ.get('PUBLIC_BACKEND_URL', '').rstrip('/')
ENABLE_DJANGO_RQ_DASHBOARD = env_bool('ENABLE_DJANGO_RQ_DASHBOARD', False)

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'dev-only-insecure-secret-key'
    else:
        raise ImproperlyConfigured('SECRET_KEY must be set when DEBUG=False.')

_allowed_hosts = os.environ.get('ALLOWED_HOSTS', '')
if _allowed_hosts:
    ALLOWED_HOSTS = [host.strip() for host in _allowed_hosts.split(',') if host.strip()]
elif DEBUG:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']
else:
    raise ImproperlyConfigured('ALLOWED_HOSTS must be set when DEBUG=False.')

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'accounts',
    'products',
    'orders',
    'delivery',
    'vendors',
    'notifications',
    'support',
    'invoices',
    'files',
    'django_rq',
    'channels',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'backend.request_logging_middleware.RequestLoggingMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'
ASGI_APPLICATION = 'backend.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.environ.get('DB_NAME', 'nc_shopping_app'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'admin'),
        'HOST': os.environ.get('DB_HOST', 'db'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTH_USER_MODEL = 'accounts.User'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & Media
# ---------------------------------------------------------------------------

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media: use S3 when USE_S3=true, otherwise local filesystem.
USE_S3 = env_bool('USE_S3', False)
FILE_UPLOAD_MAX_SIZE = int(os.environ.get('FILE_UPLOAD_MAX_SIZE', 10 * 1024 * 1024))
FILE_UPLOAD_ALLOWED_CONTENT_TYPES = [
    content_type.strip()
    for content_type in os.environ.get(
        'FILE_UPLOAD_ALLOWED_CONTENT_TYPES',
        ','.join([
            'image/jpeg',
            'image/png',
            'image/webp',
            'application/pdf',
        ]),
    ).split(',')
    if content_type.strip()
]

if USE_S3:
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID') or None
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY') or None
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', '')
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'ap-southeast-2')
    AWS_LOCATION = os.environ.get('AWS_LOCATION', 'media').strip('/') or 'media'
    AWS_S3_ENDPOINT_URL = os.environ.get('AWS_S3_ENDPOINT_URL') or None
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_S3_CUSTOM_DOMAIN') or None

    if not AWS_STORAGE_BUCKET_NAME:
        raise ImproperlyConfigured('AWS_STORAGE_BUCKET_NAME must be set when USE_S3=true.')

    _s3_options = {
        'bucket_name': AWS_STORAGE_BUCKET_NAME,
        'region_name': AWS_S3_REGION_NAME,
        'default_acl': AWS_DEFAULT_ACL,
        'file_overwrite': AWS_S3_FILE_OVERWRITE,
        'location': AWS_LOCATION,
        'querystring_auth': AWS_QUERYSTRING_AUTH,
    }
    if AWS_ACCESS_KEY_ID:
        _s3_options['access_key'] = AWS_ACCESS_KEY_ID
    if AWS_SECRET_ACCESS_KEY:
        _s3_options['secret_key'] = AWS_SECRET_ACCESS_KEY
    if AWS_S3_ENDPOINT_URL:
        _s3_options['endpoint_url'] = AWS_S3_ENDPOINT_URL
    if AWS_S3_CUSTOM_DOMAIN:
        _s3_options['custom_domain'] = AWS_S3_CUSTOM_DOMAIN

    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3.S3Storage',
            'OPTIONS': _s3_options,
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }
    MEDIA_URL = (
        f'https://{AWS_S3_CUSTOM_DOMAIN}/{AWS_LOCATION}/'
        if AWS_S3_CUSTOM_DOMAIN
        else f'https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/{AWS_LOCATION}/'
    )
else:
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

CORS_ALLOW_ALL_ORIGINS = os.environ.get('CORS_ALLOW_ALL_ORIGINS', 'False') == 'True'
CORS_ALLOW_CREDENTIALS = env_bool('CORS_ALLOW_CREDENTIALS', True)
_cors_origins = os.environ.get('CORS_ALLOWED_ORIGINS', '')
if _cors_origins:
    CORS_ALLOWED_ORIGINS = _cors_origins.split(',')
elif not CORS_ALLOW_ALL_ORIGINS:
    CORS_ALLOWED_ORIGINS = []

# ---------------------------------------------------------------------------
# REST Framework
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'accounts.authentication.OptionalJWTAuthentication',
    ),
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.environ.get('ACCESS_TOKEN_LIFETIME_MINUTES', '15'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.environ.get('REFRESH_TOKEN_LIFETIME_DAYS', '7'))),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

AUTH_REFRESH_COOKIE_NAME = os.environ.get('AUTH_REFRESH_COOKIE_NAME', 'nexconnect_refresh')
AUTH_REFRESH_COOKIE_SAMESITE = os.environ.get('AUTH_REFRESH_COOKIE_SAMESITE', 'Lax')
AUTH_REFRESH_COOKIE_SECURE = os.environ.get(
    'AUTH_REFRESH_COOKIE_SECURE',
    'False' if DEBUG else 'True',
) == 'True'
AUTH_REFRESH_COOKIE_DOMAIN = os.environ.get('AUTH_REFRESH_COOKIE_DOMAIN', '')

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

_smtp_configured = bool(os.environ.get('SMTP_HOST') and os.environ.get('SMTP_EMAIL'))
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend' if _smtp_configured else 'django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST = os.environ.get('SMTP_HOST') or os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('SMTP_PORT') or os.environ.get('EMAIL_PORT', 1025))
EMAIL_HOST_USER = os.environ.get('SMTP_EMAIL') or os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('SMTP_APP_PASSWORD') or os.environ.get('EMAIL_HOST_PASSWORD', '')
_smtp_secure = (os.environ.get('SMTP_SECURE') or os.environ.get('EMAIL_USE_TLS', 'False')).strip().lower()
EMAIL_USE_SSL = _smtp_secure in ('ssl', 'smtps') or (_smtp_secure in ('true', '1', 'yes') and EMAIL_PORT == 465)
EMAIL_USE_TLS = not EMAIL_USE_SSL and _smtp_secure in ('true', '1', 'yes', 'tls', 'starttls')
DEFAULT_FROM_EMAIL = (
    os.environ.get('EMAIL_FROM_ADDRESS')
    or os.environ.get('FROM_EMAIL')
    or os.environ.get('DEFAULT_FROM_EMAIL', 'no-reply@nextou.in')
)
DEFAULT_FROM_NAME = os.environ.get('EMAIL_FROM_NAME') or os.environ.get('FROM_NAME', 'Nextou')
BRAND_NAME = os.environ.get('BRAND_NAME', 'Nextou')
BRAND_TAGLINE = os.environ.get('BRAND_TAGLINE', 'Fast. Fresh. Delivered. \u26a1')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://nex-connect.in')
CUSTOMER_APP_URL = os.environ.get('CUSTOMER_APP_URL', FRONTEND_URL)
VENDOR_APP_URL = os.environ.get('VENDOR_APP_URL', FRONTEND_URL)
ADMIN_PANEL_URL = os.environ.get('ADMIN_PANEL_URL', FRONTEND_URL)
SUPPORT_EMAIL = os.environ.get('SUPPORT_EMAIL', 'support@nextou.in')
SUPPORT_PHONE = os.environ.get('SUPPORT_PHONE', '+91 80 1234 5678')
SUPPORT_HOURS = os.environ.get('SUPPORT_HOURS', 'Mon - Sun: 7AM - 11PM')
HELP_URL = os.environ.get('HELP_URL', f"{CUSTOMER_APP_URL.rstrip('/')}/help" if CUSTOMER_APP_URL else '')
FAQ_URL = os.environ.get('FAQ_URL', f"{CUSTOMER_APP_URL.rstrip('/')}/help/faq" if CUSTOMER_APP_URL else '')
SUPPORT_URL = os.environ.get('SUPPORT_URL', f"{CUSTOMER_APP_URL.rstrip('/')}/help" if CUSTOMER_APP_URL else '')
ADMIN_VENDOR_REVIEW_EMAIL = os.environ.get('ADMIN_VENDOR_REVIEW_EMAIL', '')
WELCOME_COUPON_CODE = os.environ.get('WELCOME_COUPON_CODE', 'NEXTOU25')
OTP_EXPIRY_MINUTES = int(os.environ.get('OTP_EXPIRY_MINUTES', '10'))
EMAIL_VERIFICATION_EXPIRY_MINUTES = int(os.environ.get('EMAIL_VERIFICATION_EXPIRY_MINUTES', '15'))
CUSTOMER_AUTH_EXPOSE_DEV_OTP = os.environ.get('CUSTOMER_AUTH_EXPOSE_DEV_OTP', 'False') in ('True', 'true', '1', 'yes')

# ---------------------------------------------------------------------------
# Firebase / FCM
# ---------------------------------------------------------------------------

# Path to the Firebase service account JSON downloaded from Firebase Console.
# Firebase Console → Project Settings → Service Accounts → Generate new private key.
FIREBASE_SERVICE_ACCOUNT_PATH = os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH', '')

# Legacy — kept for reference; actual auth uses the service account file above.
FCM_SERVER_KEY = os.environ.get('FCM_SERVER_KEY', '')

# ---------------------------------------------------------------------------
# Razorpay
# ---------------------------------------------------------------------------

RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '')

# ---------------------------------------------------------------------------
# RQ (background jobs)
# ---------------------------------------------------------------------------

RQ_QUEUES = {
    'default': {
        'HOST': os.environ.get('REDIS_HOST', 'localhost'),
        'PORT': int(os.environ.get('REDIS_PORT', 6379)),
        'DB': 0,
        'DEFAULT_TIMEOUT': 360,
    },
}

# ---------------------------------------------------------------------------
# Django Channels
# ---------------------------------------------------------------------------

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(os.environ.get('REDIS_HOST', '127.0.0.1'), int(os.environ.get('REDIS_PORT', 6379)))],
        },
    },
}

# ---------------------------------------------------------------------------
# Cache (django-redis)
# ---------------------------------------------------------------------------

API_PUBLIC_CACHE_TTL_SECONDS = int(os.environ.get('API_PUBLIC_CACHE_TTL_SECONDS', 120))
API_REFERENCE_CACHE_TTL_SECONDS = int(os.environ.get('API_REFERENCE_CACHE_TTL_SECONDS', 300))

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"redis://{os.environ.get('REDIS_HOST', '127.0.0.1')}:{os.environ.get('REDIS_PORT', 6379)}/1",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    }
}

# ---------------------------------------------------------------------------
# drf-spectacular (OpenAPI)
# ---------------------------------------------------------------------------

SPECTACULAR_SETTINGS = {
    'TITLE': 'Nextou API',
    'DESCRIPTION': 'Multi-vendor delivery platform API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

# ---------------------------------------------------------------------------
# Sentry
# ---------------------------------------------------------------------------

_sentry_dsn = os.environ.get('SENTRY_DSN', '')
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        environment=os.environ.get('SENTRY_ENVIRONMENT', 'production'),
        traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
        send_default_pii=False,
    )

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_requested_log_level = os.environ.get('APP_LOG_LEVEL', 'WARNING').upper()
if _requested_log_level in {'NOTSET', 'DEBUG', 'INFO'}:
    APP_LOG_LEVEL = 'WARNING'
else:
    APP_LOG_LEVEL = _requested_log_level
APP_LOG_FILE_NAME = os.environ.get('APP_LOG_FILE_NAME', 'application.log')
APP_LOG_DIR = Path(os.environ.get('APP_LOG_DIR', BASE_DIR / 'runtime_logs'))
APP_LOG_S3_PREFIX = (os.environ.get('APP_LOG_S3_PREFIX', 'logs') or 'logs').strip('/') or 'logs'
APP_LOG_UPLOAD_INTERVAL_SECONDS = int(os.environ.get('APP_LOG_UPLOAD_INTERVAL_SECONDS', '30'))
APP_LOG_TIMEZONE = os.environ.get('APP_LOG_TIMEZONE', 'Asia/Kolkata')
APP_LOG_RQ_QUEUE = os.environ.get('APP_LOG_RQ_QUEUE', 'default')
APP_LOG_S3_BUCKET = os.environ.get('AWS_STORAGE_BUCKET_NAME', '')
ENABLE_S3_LOG_ARCHIVE = env_bool('ENABLE_S3_LOG_ARCHIVE', USE_S3 and bool(APP_LOG_S3_BUCKET))

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'request_context': {
            '()': 'helpers.logging_filters.RequestContextFilter',
        },
    },
    'formatters': {
        'standard': {
            'format': (
                '%(asctime)s %(levelname)s [%(name)s] '
                '[user=%(username)s request_id=%(request_id)s] %(message)s'
            ),
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': APP_LOG_LEVEL,
            'formatter': 'standard',
            'filters': ['request_context'],
        },
        'per_user_daily': {
            'class': 'helpers.logging_handlers.PerUserDailyS3Handler',
            'level': APP_LOG_LEVEL,
            'formatter': 'standard',
            'filters': ['request_context'],
            'local_base_dir': str(APP_LOG_DIR),
            'filename': APP_LOG_FILE_NAME,
            's3_enabled': ENABLE_S3_LOG_ARCHIVE,
            's3_bucket': APP_LOG_S3_BUCKET,
            's3_prefix': APP_LOG_S3_PREFIX,
            's3_region_name': os.environ.get('AWS_S3_REGION_NAME', 'ap-southeast-2'),
            's3_endpoint_url': os.environ.get('AWS_S3_ENDPOINT_URL') or None,
            'aws_access_key_id': os.environ.get('AWS_ACCESS_KEY_ID') or None,
            'aws_secret_access_key': os.environ.get('AWS_SECRET_ACCESS_KEY') or None,
            'rq_queue_name': APP_LOG_RQ_QUEUE,
            'upload_interval_seconds': APP_LOG_UPLOAD_INTERVAL_SECONDS,
            'timezone_name': APP_LOG_TIMEZONE,
        },
    },
    'root': {
        'handlers': ['console', 'per_user_daily'],
        'level': APP_LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'per_user_daily'],
            'level': APP_LOG_LEVEL,
            'propagate': False,
        },
        'backend.request': {
            'handlers': ['console', 'per_user_daily'],
            'level': APP_LOG_LEVEL,
            'propagate': False,
        },
    },
}

# ---------------------------------------------------------------------------
# Security (production hardening — active when DEBUG=False)
# ---------------------------------------------------------------------------

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
