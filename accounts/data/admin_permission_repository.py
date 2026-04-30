from accounts.models import AdminPermissionGrant
from vendors.data.base import BaseRepository


class AdminPermissionGrantRepository(BaseRepository):
    def __init__(self):
        super().__init__(AdminPermissionGrant)

    @staticmethod
    def list(user_id=None, permission=None, search=None):
        queryset = AdminPermissionGrant.objects.select_related(
            'user',
            'granted_by',
        ).order_by('user__username', 'permission')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if permission:
            queryset = queryset.filter(permission=permission)
        if search:
            queryset = queryset.filter(user__username__icontains=search)
        return queryset
