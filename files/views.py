from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import AdminPermissionGrant
from files.actions import UploadFileAction
from files.data import UploadedFileRepository
from files.serializers import UploadedFileSerializer


def user_can_manage_files(user) -> bool:
    if not (user and user.is_authenticated and user.role == 'admin'):
        return False
    if user.is_superuser:
        return True
    return AdminPermissionGrant.objects.filter(
        user=user,
        permission__in=['support.manage', 'orders.manage', 'vendors.manage', 'dispatch.manage', 'finance.manage'],
    ).exists()


def user_can_access_upload(user, uploaded) -> bool:
    if uploaded.uploaded_by_id == getattr(user, 'id', None):
        return True
    return user_can_manage_files(user)


class UploadedFileListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        repository = UploadedFileRepository()
        files = repository.list_all() if user_can_manage_files(request.user) else repository.list_for_user(request.user)
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
        if not user_can_access_upload(request.user, uploaded):
            raise PermissionDenied('You do not have access to this file.')
        serializer = UploadedFileSerializer(uploaded, context={'request': request})
        return Response(serializer.data)
