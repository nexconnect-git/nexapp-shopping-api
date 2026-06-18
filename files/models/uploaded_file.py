import uuid

from django.conf import settings
from django.db import models

from helpers.upload_paths import build_upload_path


USE_OF_IMAGE_CHOICES = (
    ('profile_image', 'Profile image'),
    ('cover_image', 'Cover image'),
    ('product_image', 'Product image'),
    ('category_image', 'Category image'),
    ('vendor_document', 'Vendor document'),
    ('delivery_document', 'Delivery document'),
    ('order_attachment', 'Order attachment'),
    ('delivery_proof', 'Delivery proof'),
    ('transaction_proof', 'Transaction proof'),
    ('invoice', 'Invoice'),
    ('banner_image', 'Banner image'),
    ('general_upload', 'General upload'),
)


def uploaded_file_path(instance, filename):
    return build_upload_path(instance, filename, instance.use_of_image)


class UploadedFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_upload_id = models.CharField(max_length=80, unique=True, blank=True, null=True)
    original_filename = models.CharField(max_length=255)
    use_of_image = models.CharField(max_length=40, choices=USE_OF_IMAGE_CHOICES, default='general_upload')
    file = models.FileField(upload_to=uploaded_file_path)
    content_type = models.CharField(max_length=120)
    size = models.PositiveBigIntegerField()
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='uploaded_files',
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'files'
        ordering = ['-created_at']

    def __str__(self):
        return self.original_filename
