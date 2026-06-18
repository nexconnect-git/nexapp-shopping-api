from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from files.actions import UploadFileAction
from files.serializers import UploadedFileSerializer


class UploadedFileUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        uploaded = UploadFileAction().execute(
            request.FILES.get('file'),
            request.user,
            request.data.get('use_of_image', 'general_upload'),
            request.data.get('client_upload_id', ''),
        )
        serializer = UploadedFileSerializer(uploaded, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
