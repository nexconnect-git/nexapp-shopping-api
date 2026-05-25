from rest_framework import serializers

from helpers.serializer_fields import SafeImageField
from products.models import ProductImage


class ProductImageSerializer(serializers.ModelSerializer):
    """Serializer for ProductImage; builds absolute URLs when request is in context."""

    image = SafeImageField(required=False, allow_null=True)

    class Meta:
        model = ProductImage
        fields = ["id", "image", "is_primary", "is_ai_generated", "display_order"]
        read_only_fields = ["id"]
