from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.utils._os import safe_join
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

try:
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
except ImportError:
    BotoCoreError = ClientError = NoCredentialsError = Exception


class MediaFileView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, path):
        clean_path = path.lstrip('/')
        if not clean_path or '..' in Path(clean_path).parts:
            raise Http404

        try:
            if default_storage.exists(clean_path):
                return self._cached_file_response(
                    default_storage.open(clean_path, 'rb'),
                    Path(clean_path).name,
                )
        except (BotoCoreError, ClientError, NoCredentialsError, ValueError):
            pass

        local_media_root = getattr(settings, 'MEDIA_ROOT', None) or Path(settings.BASE_DIR) / 'media'
        try:
            local_path = safe_join(str(local_media_root), clean_path)
        except ValueError as exc:
            raise Http404 from exc

        if Path(local_path).is_file():
            return self._cached_file_response(open(local_path, 'rb'), Path(local_path).name)

        raise Http404

    def _cached_file_response(self, file_obj, filename):
        response = FileResponse(file_obj, filename=filename)
        response['Cache-Control'] = 'public, max-age=86400'
        return response
