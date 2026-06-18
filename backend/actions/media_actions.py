from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import Http404
from django.utils._os import safe_join

from helpers.media_access_helpers import can_access_media

try:
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
except ImportError:
    BotoCoreError = ClientError = NoCredentialsError = Exception


class GetMediaFileAction:
    def execute(self, request, path):
        clean_path = path.lstrip('/')
        if not clean_path or '..' in Path(clean_path).parts:
            raise Http404

        allowed, is_public = can_access_media(request, clean_path)
        if not allowed:
            raise Http404

        storage_file = self._open_storage_file(clean_path)
        if storage_file:
            return storage_file, Path(clean_path).name, is_public

        local_file = self._open_local_file(clean_path)
        if local_file:
            return local_file, Path(clean_path).name, is_public

        raise Http404

    def _open_storage_file(self, clean_path):
        try:
            if default_storage.exists(clean_path):
                return default_storage.open(clean_path, 'rb')
        except (BotoCoreError, ClientError, NoCredentialsError, ValueError):
            return None
        return None

    def _open_local_file(self, clean_path):
        local_media_root = getattr(settings, 'MEDIA_ROOT', None) or Path(settings.BASE_DIR) / 'media'
        try:
            local_path = safe_join(str(local_media_root), clean_path)
        except ValueError as exc:
            raise Http404 from exc

        if Path(local_path).is_file():
            return open(local_path, 'rb')
        return None
