from hashlib import sha1
from urllib.parse import quote

from django.conf import settings

try:
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
except ImportError:
    BotoCoreError = ClientError = NoCredentialsError = Exception


def proxied_media_url(file_field, request=None):
    if not file_field:
        return None

    name = getattr(file_field, 'name', '') or ''
    if not name:
        return None

    path = quote(name.lstrip('/'), safe='/')
    version = sha1(name.encode('utf-8')).hexdigest()[:12]
    url = f'/api/media/{path}/?v={version}'
    public_backend_url = getattr(settings, 'PUBLIC_BACKEND_URL', '')
    if public_backend_url:
        return f'{public_backend_url}{url}'
    if getattr(settings, 'DEBUG', False):
        return f'http://localhost:8000{url}'
    if request:
        return request.build_absolute_uri(url)
    return url


def safe_media_url(file_field, request=None, default=None):
    if not file_field:
        return default

    proxied = proxied_media_url(file_field, request=request)
    if proxied:
        return proxied

    try:
        url = file_field.url
    except (BotoCoreError, ClientError, NoCredentialsError, ValueError):
        return default

    if request and url.startswith('/'):
        return request.build_absolute_uri(url)
    return url
