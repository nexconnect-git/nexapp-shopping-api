from pathlib import Path

from accounts.data.admin_permission_repository import AdminPermissionGrantRepository
from backend.data import MediaAccessRepository
from helpers.upload_paths import clean_path_segment


PUBLIC_MEDIA_USES = {
    'profile_image',
    'cover_image',
    'product_image',
    'category_image',
    'banner_image',
}

PRIVATE_USE_PERMISSIONS = {
    'vendor_document': {'vendors.manage'},
    'delivery_document': {'dispatch.manage'},
    'order_attachment': {'support.manage', 'orders.manage'},
    'delivery_proof': {'orders.manage', 'dispatch.manage'},
    'transaction_proof': {'orders.manage', 'finance.manage'},
    'invoice': {'orders.manage', 'finance.manage'},
    'general_upload': {'settings.manage'},
}


def use_segment_for_path(clean_path):
    parts = Path(clean_path).parts
    if len(parts) >= 4 and parts[0] == 'vendors' and parts[2] == 'documents':
        return 'vendor_document'
    if len(parts) >= 4 and parts[0] == 'delivery_partners' and parts[2] == 'documents':
        return 'delivery_document'
    if len(parts) >= 3:
        return parts[2]
    return ''


def owner_segment_for_path(clean_path):
    parts = Path(clean_path).parts
    if parts:
        return parts[0]
    return ''


def is_admin_allowed_for_media(user, use_segment):
    if not (user and user.is_authenticated and user.role == 'admin'):
        return False
    if user.is_superuser:
        return True
    allowed = PRIVATE_USE_PERMISSIONS.get(use_segment) or {'settings.manage'}
    return AdminPermissionGrantRepository.exists_for_permissions(user, allowed)


def is_owner_path(user, clean_path):
    if not (user and user.is_authenticated):
        return False
    return owner_segment_for_path(clean_path) == clean_path_segment(user.username, 'system')


def is_assigned_order_media(user, clean_path, repository: MediaAccessRepository = None):
    if not (user and user.is_authenticated):
        return False

    repository = repository or MediaAccessRepository()
    return (
        repository.delivery_partner_has_order_media(user, clean_path)
        or repository.delivery_partner_has_issue_attachment(user, clean_path)
    )


def can_access_media(request, clean_path, repository: MediaAccessRepository = None):
    repository = repository or MediaAccessRepository()
    uploaded = repository.get_uploaded_file(clean_path)
    if uploaded:
        if uploaded.uploaded_by_id == getattr(request.user, 'id', None):
            return True, False
        return is_admin_allowed_for_media(request.user, uploaded.use_of_image), False

    use_segment = use_segment_for_path(clean_path)
    if use_segment in PUBLIC_MEDIA_USES:
        return True, True

    if is_owner_path(request.user, clean_path):
        return True, False
    if is_assigned_order_media(request.user, clean_path, repository=repository):
        return True, False
    return is_admin_allowed_for_media(request.user, use_segment), False
