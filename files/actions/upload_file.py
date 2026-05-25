from django.conf import settings
from rest_framework.exceptions import ValidationError

from files.data import UploadedFileRepository
from files.models import USE_OF_IMAGE_CHOICES


VALID_USE_OF_IMAGE_VALUES = {choice[0] for choice in USE_OF_IMAGE_CHOICES}


class UploadFileAction:
    def __init__(self, repository=None):
        self.repository = repository or UploadedFileRepository()

    def execute(self, uploaded_file, user, use_of_image='general_upload', client_upload_id=''):
        existing_upload = self.repository.get_by_client_upload_id(client_upload_id)
        if existing_upload:
            return existing_upload

        if not uploaded_file:
            raise ValidationError({'file': 'A file is required.'})

        if use_of_image not in VALID_USE_OF_IMAGE_VALUES:
            raise ValidationError({'use_of_image': 'Select a valid upload usage.'})

        size = getattr(uploaded_file, 'size', 0) or 0
        if size <= 0:
            raise ValidationError({'file': 'Uploaded file cannot be empty.'})

        max_size = getattr(settings, 'FILE_UPLOAD_MAX_SIZE', 10 * 1024 * 1024)
        if size > max_size:
            max_mb = max_size / (1024 * 1024)
            raise ValidationError({'file': f'File size must be {max_mb:g} MB or smaller.'})

        content_type = getattr(uploaded_file, 'content_type', '') or 'application/octet-stream'
        allowed_types = getattr(settings, 'FILE_UPLOAD_ALLOWED_CONTENT_TYPES', [])
        if allowed_types and content_type not in allowed_types:
            raise ValidationError({'file': f'File type {content_type} is not allowed.'})

        uploaded_by = user if getattr(user, 'is_authenticated', False) else None
        return self.repository.create(
            original_filename=uploaded_file.name,
            client_upload_id=client_upload_id or None,
            use_of_image=use_of_image,
            file=uploaded_file,
            content_type=content_type,
            size=size,
            uploaded_by=uploaded_by,
        )
