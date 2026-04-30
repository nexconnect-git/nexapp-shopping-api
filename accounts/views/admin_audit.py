from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from accounts.data.audit_repository import AdminAuditLogRepository
from accounts.permissions import IsAdminRole
from accounts.serializers.audit_serializers import AdminAuditLogSerializer


class AdminAuditLogPagination(PageNumberPagination):
    page_size = 20


class AdminAuditLogListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = AdminAuditLogSerializer
    pagination_class = AdminAuditLogPagination

    def get_queryset(self):
        params = self.request.query_params
        return AdminAuditLogRepository.list(
            action=params.get('action'),
            entity_type=params.get('entity_type'),
            actor_id=params.get('actor'),
            search=params.get('search'),
        )
