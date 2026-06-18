from accounts.data.admin_permission_repository import AdminPermissionGrantRepository


FILE_MANAGER_PERMISSIONS = [
    'support.manage',
    'orders.manage',
    'vendors.manage',
    'dispatch.manage',
    'finance.manage',
]


def user_can_manage_files(user) -> bool:
    if not (user and user.is_authenticated and user.role == 'admin'):
        return False
    if user.is_superuser:
        return True
    return AdminPermissionGrantRepository.exists_for_permissions(
        user,
        FILE_MANAGER_PERMISSIONS,
    )


def user_can_access_upload(user, uploaded) -> bool:
    if uploaded.uploaded_by_id == getattr(user, 'id', None):
        return True
    return user_can_manage_files(user)
