import uuid

from django.db import models


class CustomerContentBlock(models.Model):
    class Placement(models.TextChoices):
        HOME_AD = 'home_ad', 'Home promo card'
        HOME_ENGAGEMENT = 'home_engagement', 'Home engagement banner'
        OFFERS_SHOP = 'offers_shop', 'Offers page banner'
        SEARCH_AD = 'search_ad', 'Search page banner'
        STORE_LISTING_AD = 'store_listing_ad', 'Store listing banner'
        STORE_DETAIL_AD = 'store_detail_ad', 'Store detail banner'

    class Template(models.TextChoices):
        SOFT_CARD = 'soft_card', 'Soft promo card'
        CLUB_BANNER = 'club_banner', 'Club banner'
        IMAGE_CARD = 'image_card', 'Image card'

    class Tone(models.TextChoices):
        PURPLE = 'purple', 'Purple'
        GREEN = 'green', 'Green'
        ORANGE = 'orange', 'Orange'
        RED = 'red', 'Red'
        BLUE = 'blue', 'Blue'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    placement = models.CharField(max_length=32, choices=Placement.choices)
    template = models.CharField(
        max_length=32,
        choices=Template.choices,
        default=Template.SOFT_CARD,
    )
    eyebrow = models.CharField(max_length=40, blank=True)
    title = models.CharField(max_length=100)
    subtitle = models.CharField(max_length=220, blank=True)
    cta_label = models.CharField(max_length=40, default='Shop now')
    cta_url = models.CharField(max_length=255, default='/stores')
    icon = models.CharField(max_length=48, blank=True)
    tone = models.CharField(max_length=16, choices=Tone.choices, default=Tone.PURPLE)
    image = models.URLField(max_length=500, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['placement', 'display_order', 'created_at']
        indexes = [
            models.Index(fields=['placement', 'is_active', 'display_order']),
            models.Index(fields=['starts_at', 'ends_at']),
        ]

    def __str__(self):
        return f'{self.get_placement_display()}: {self.title}'
