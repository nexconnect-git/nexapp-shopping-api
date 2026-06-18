from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from files.data import UploadedFileRepository
from files.helpers import user_can_access_upload
from files.serializers import UploadedFileSerializer


class UploadedFileDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        uploaded = UploadedFileRepository().get_by_id(pk, select_related=['uploaded_by'])
        if not uploaded:
            return Response({'detail': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not user_can_access_upload(request.user, uploaded):
            raise PermissionDenied('You do not have access to this file.')
        serializer = UploadedFileSerializer(uploaded, context={'request': request})
        return Response(serializer.data)
