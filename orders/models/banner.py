"""Platform promotional banners shown in the customer app home carousel."""

from django.db import models
import uuid


class PlatformBanner(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=100)
    subtitle = models.CharField(max_length=200, blank=True)
    badge_text = models.CharField(max_length=40, blank=True)
    cta_label = models.CharField(max_length=40, default='Order Now')
    cta_url = models.CharField(max_length=255, default='/shops')
    image = models.ImageField(upload_to='banners/', null=True, blank=True)
    bg_gradient = models.CharField(
        max_length=120,
        default='linear-gradient(135deg,#6c63ff,#5046e4)',
        help_text='CSS gradient string used as background when no image is set.',
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'created_at']

    def __str__(self):
        return self.title
