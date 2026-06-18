from django.http import FileResponse
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from backend.actions.media_actions import GetMediaFileAction


class MediaFileView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, path):
        file_obj, filename, is_public = GetMediaFileAction().execute(request, path)
        response = FileResponse(file_obj, filename=filename)
        response['Cache-Control'] = 'public, max-age=86400' if is_public else 'private, no-store'
        return response
