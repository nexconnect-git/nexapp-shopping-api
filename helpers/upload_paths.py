from pathlib import Path
from uuid import uuid4

from django.utils import timezone
from django.utils.deconstruct import deconstructible
from django.utils.text import get_valid_filename, slugify


def _get_nested_attr(instance, path):
    value = instance
    for part in path.split('.'):
        value = getattr(value, part, None)
        if value is None:
            return None
    return value


def _username_from_user(user):
    username = getattr(user, 'username', None)
    if username:
        return username
    user_id = getattr(user, 'id', None)
    if user_id:
        return str(user_id)
    return ''


def username_for_upload(instance):
    for path in (
        'uploaded_by',
        'user',
        'customer',
        'sender',
        'recipient',
        'created_by',
        'delivery_partner',
        'vendor.user',
        'product.vendor.user',
        'catalog_product.created_by',
        'proposal.vendor.user',
        'issue.customer',
        'order.customer',
        'order.vendor.user',
    ):
        user = _get_nested_attr(instance, path)
        username = _username_from_user(user)
        if username:
            return username
    return 'system'


def clean_path_segment(value, fallback):
    segment = slugify(str(value or '').strip()).replace('-', '_')
    return segment or fallback


def build_upload_path(instance, filename, use_of_image):
    username = clean_path_segment(username_for_upload(instance), 'system')
    date_segment = timezone.localdate().strftime('%d%m%Y')
    use_segment = clean_path_segment(use_of_image, 'general')
    filename = get_valid_filename(Path(filename).name)
    return f'{username}/{date_segment}/{use_segment}/{filename}'


def _private_document_filename(filename, prefix=''):
    suffix = Path(get_valid_filename(Path(filename).name)).suffix.lower()
    prefix_segment = clean_path_segment(prefix, '')
    if prefix_segment:
        return f'{prefix_segment}-{uuid4().hex}{suffix}'
    return f'{uuid4().hex}{suffix}'


def _instance_id_segment(instance, attr, fallback):
    value = _get_nested_attr(instance, attr)
    if value:
        return get_valid_filename(str(value).strip()) or fallback
    return fallback


@deconstructible
class UserDateUploadPath:
    def __init__(self, use_of_image):
        self.use_of_image = use_of_image

    def __call__(self, instance, filename):
        return build_upload_path(instance, filename, self.use_of_image)


@deconstructible
class VendorDocumentUploadPath:
    def __call__(self, instance, filename):
        vendor_id = _instance_id_segment(instance, 'vendor.id', 'unassigned_vendor')
        document_type = clean_path_segment(getattr(instance, 'document_type', ''), 'document')
        return (
            f'vendors/{vendor_id}/documents/license/'
            f'{_private_document_filename(filename, document_type)}'
        )


@deconstructible
class DeliveryPartnerDocumentUploadPath:
    def __init__(self, document_type='id_proof'):
        self.document_type = document_type

    def __call__(self, instance, filename):
        partner_id = _instance_id_segment(instance, 'id', 'unassigned_partner')
        document_type = clean_path_segment(self.document_type, 'document')
        return (
            f'delivery_partners/{partner_id}/documents/license/'
            f'{_private_document_filename(filename, document_type)}'
        )
