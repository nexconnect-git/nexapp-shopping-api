from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.actions.audit_actions import CreateAdminAuditLogAction
from accounts.data.admin_permission_repository import AdminPermissionGrantRepository
from accounts.models import AdminPermissionGrant
from accounts.permissions import IsSuperUser
from accounts.serializers.rbac_serializers import AdminPermissionGrantSerializer


class AdminPermissionGrantPagination(PageNumberPagination):
    page_size = 20


class AdminPermissionGrantListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsSuperUser]
    serializer_class = AdminPermissionGrantSerializer
    pagination_class = AdminPermissionGrantPagination

    def get_queryset(self):
        params = self.request.query_params
        return AdminPermissionGrantRepository.list(
            user_id=params.get('user'),
            permission=params.get('permission'),
            search=params.get('search'),
        )

    def perform_create(self, serializer):
        grant = serializer.save(granted_by=self.request.user)
        CreateAdminAuditLogAction().execute(
            request=self.request,
            action='permission_grant',
            entity_type='admin_permission_grant',
            entity_id=str(grant.id),
            summary=f"Granted {grant.permission} to {grant.user.username}.",
            metadata={'user': str(grant.user_id), 'permission': grant.permission},
        )


class AdminPermissionGrantDetailView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated, IsSuperUser]
    serializer_class = AdminPermissionGrantSerializer
    queryset = AdminPermissionGrant.objects.select_related('user', 'granted_by')

    def destroy(self, request, *args, **kwargs):
        grant = self.get_object()
        metadata = {'user': str(grant.user_id), 'permission': grant.permission}
        summary = f"Revoked {grant.permission} from {grant.user.username}."
        self.perform_destroy(grant)
        CreateAdminAuditLogAction().execute(
            request=request,
            action='permission_revoke',
            entity_type='admin_permission_grant',
            entity_id=str(grant.id),
            summary=summary,
            metadata=metadata,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
