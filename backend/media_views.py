from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.utils._os import safe_join
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from accounts.models import AdminPermissionGrant
from files.models import UploadedFile
from helpers.upload_paths import clean_path_segment
from orders.models import Order
from orders.models.order_issue import OrderIssueAttachment

try:
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
except ImportError:
    BotoCoreError = ClientError = NoCredentialsError = Exception


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


def _use_segment_for_path(clean_path):
    parts = Path(clean_path).parts
    if len(parts) >= 3:
        return parts[2]
    return ''


def _owner_segment_for_path(clean_path):
    parts = Path(clean_path).parts
    if parts:
        return parts[0]
    return ''


def _is_admin_allowed(user, use_segment):
    if not (user and user.is_authenticated and user.role == 'admin'):
        return False
    if user.is_superuser:
        return True
    allowed = PRIVATE_USE_PERMISSIONS.get(use_segment) or {'settings.manage'}
    return AdminPermissionGrant.objects.filter(user=user, permission__in=allowed).exists()


def _is_owner_path(user, clean_path):
    if not (user and user.is_authenticated):
        return False
    return _owner_segment_for_path(clean_path) == clean_path_segment(user.username, 'system')


def _is_assigned_order_media(user, clean_path):
    if not (user and user.is_authenticated):
        return False

    order_media = (
        Order.objects.filter(delivery_partner=user, delivery_photo=clean_path)
        | Order.objects.filter(delivery_partner=user, transaction_photo=clean_path)
    )
    if order_media.exists():
        return True

    return OrderIssueAttachment.objects.filter(
        file=clean_path,
        issue__order__delivery_partner=user,
    ).exists()


def _can_access_media(request, clean_path):
    uploaded = UploadedFile.objects.filter(file=clean_path).select_related('uploaded_by').first()
    if uploaded:
        if uploaded.uploaded_by_id == getattr(request.user, 'id', None):
            return True, False
        return _is_admin_allowed(request.user, uploaded.use_of_image), False

    use_segment = _use_segment_for_path(clean_path)
    if use_segment in PUBLIC_MEDIA_USES:
        return True, True

    if _is_owner_path(request.user, clean_path):
        return True, False
    if _is_assigned_order_media(request.user, clean_path):
        return True, False
    return _is_admin_allowed(request.user, use_segment), False


class MediaFileView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, path):
        clean_path = path.lstrip('/')
        if not clean_path or '..' in Path(clean_path).parts:
            raise Http404

        allowed, is_public = _can_access_media(request, clean_path)
        if not allowed:
            raise Http404

        try:
            if default_storage.exists(clean_path):
                return self._cached_file_response(
                    default_storage.open(clean_path, 'rb'),
                    Path(clean_path).name,
                    is_public=is_public,
                )
        except (BotoCoreError, ClientError, NoCredentialsError, ValueError):
            pass

        local_media_root = getattr(settings, 'MEDIA_ROOT', None) or Path(settings.BASE_DIR) / 'media'
        try:
            local_path = safe_join(str(local_media_root), clean_path)
        except ValueError as exc:
            raise Http404 from exc

        if Path(local_path).is_file():
            return self._cached_file_response(open(local_path, 'rb'), Path(local_path).name, is_public=is_public)

        raise Http404

    def _cached_file_response(self, file_obj, filename, is_public=False):
        response = FileResponse(file_obj, filename=filename)
        response['Cache-Control'] = 'public, max-age=86400' if is_public else 'private, no-store'
        return response
