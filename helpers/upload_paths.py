from pathlib import Path

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


@deconstructible
class UserDateUploadPath:
    def __init__(self, use_of_image):
        self.use_of_image = use_of_image

    def __call__(self, instance, filename):
        return build_upload_path(instance, filename, self.use_of_image)
