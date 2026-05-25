from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from files.actions import UploadFileAction
from files.data import UploadedFileRepository
from files.serializers import UploadedFileSerializer


class UploadedFileListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        files = UploadedFileRepository().list_all()
        serializer = UploadedFileSerializer(files, many=True, context={'request': request})
        return Response(serializer.data)


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


class UploadedFileDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        uploaded = UploadedFileRepository().get_by_id(pk, select_related=['uploaded_by'])
        if not uploaded:
            return Response({'detail': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = UploadedFileSerializer(uploaded, context={'request': request})
        return Response(serializer.data)
