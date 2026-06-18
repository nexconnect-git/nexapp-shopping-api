from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from files.data import UploadedFileRepository
from files.helpers import user_can_manage_files
from files.serializers import UploadedFileSerializer


class UploadedFileListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        repository = UploadedFileRepository()
        files = (
            repository.list_all()
            if user_can_manage_files(request.user)
            else repository.list_for_user(request.user)
        )
        serializer = UploadedFileSerializer(files, many=True, context={'request': request})
        return Response(serializer.data)
