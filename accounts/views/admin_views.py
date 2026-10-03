from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsSuperUser
from accounts.data.user_repository import UserRepository
from accounts.serializers.user_serializers import AdminUserSerializer, AdminUserUpdateSerializer
from accounts.actions.admin_actions import UpdateAccountStatusAction
from backend.actions.admin_console_actions import AdminUserMutationAction
from accounts.actions.audit_actions import CreateAdminAuditLogAction

class AdminUserViewSet(viewsets.ModelViewSet):
    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]

    def get_queryset(self):
        return UserRepository.get_admin_users()

    def get_serializer_class(self):
        if self.action in ('update', 'partial_update'):
            return AdminUserUpdateSerializer
        return AdminUserSerializer

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, partial=True, **kwargs)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.pop('partial', False))
        serializer.is_valid(raise_exception=True)
        user = AdminUserMutationAction().execute(self.kwargs['pk'], serializer.validated_data, request)
        return Response(AdminUserSerializer(user).data)

    def perform_create(self, serializer):
        user = serializer.save()
        CreateAdminAuditLogAction().execute(request=self.request, action='create', entity_type='user', entity_id=str(user.pk), summary=f'Created administrator {user.username}.')

    def destroy(self, request, *args, **kwargs):
        self.get_object()
        AdminUserMutationAction().execute(self.kwargs['pk'], {}, request, delete=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='status')
    def update_status(self, request, pk=None):
        user = self.get_object()
        new_status = request.data.get("status")
        if not new_status:
            return Response({"error": "status is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            if new_status not in UpdateAccountStatusAction.ALLOWED_STATUSES:
                raise ValueError('Invalid account status.')
            updated_user = AdminUserMutationAction().execute(pk, {'is_active': new_status == 'active'}, request)
            return Response(self.get_serializer(updated_user).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
