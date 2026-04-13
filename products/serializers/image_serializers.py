from rest_framework import serializers

from products.models import ProductImage


class ProductImageSerializer(serializers.ModelSerializer):
    """Serializer for ProductImage; builds absolute URLs when request is in context."""

    image = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ["id", "image", "is_primary", "is_ai_generated", "display_order"]
        read_only_fields = ["id"]

    def get_image(self, obj) -> str | None:
        """Return an absolute image URL if a request is available, else relative."""
        request = self.context.get("request")
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url if obj.image else None
