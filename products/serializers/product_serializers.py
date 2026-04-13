from rest_framework import serializers
from django.utils.text import slugify

from products.models import Product
from products.serializers.category_serializers import CategorySerializer
from products.serializers.image_serializers import ProductImageSerializer
from vendors.serializers import VendorListSerializer


class ProductSerializer(serializers.ModelSerializer):
    """Full product serializer with nested vendor, category, and images."""

    images = ProductImageSerializer(many=True, read_only=True)
    vendor = VendorListSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True)
    in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "vendor", "category", "name", "slug", "description",
            "price", "compare_price", "sku", "stock", "low_stock_threshold",
            "unit", "weight", "is_available", "status", "is_featured", "average_rating",
            "total_ratings", "total_orders", "discount_percentage", "in_stock",
            "images", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "average_rating", "total_ratings", "total_orders",
            "created_at", "updated_at",
        ]


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight product serializer for list views (no nested reviews)."""

    primary_image = serializers.SerializerMethodField()
    vendor_name = serializers.CharField(source="vendor.store_name", read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True)
    in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "vendor", "name", "slug", "description", "price",
            "compare_price", "unit", "stock", "is_available", "status", "is_featured",
            "average_rating", "total_ratings", "discount_percentage", "in_stock",
            "primary_image", "vendor_name",
        ]

    def get_primary_image(self, obj) -> str | None:
        """Return the absolute URL of the primary image, or None."""
        primary = obj.images.filter(is_primary=True).first()
        if primary:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(primary.image.url)
            return primary.image.url
        return None


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Write serializer for vendor product creation and updates.

    Auto-generates a unique slug from the product name when none is supplied.
    """

    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "category", "name", "slug", "description", "price",
            "compare_price", "sku", "stock", "low_stock_threshold", "unit",
            "weight", "is_available", "status", "is_featured", "images",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {"slug": {"required": False, "allow_blank": True}}

    def _unique_slug(self, base: str, instance=None) -> str:
        """Generate a unique slug derived from ``base``.

        Appends an incrementing suffix (``-1``, ``-2``, …) until the slug
        is unique in the ``Product`` table, excluding ``instance`` if given.

        Args:
            base: The base string to slugify.
            instance: Existing ``Product`` to exclude from uniqueness check.

        Returns:
            A unique slug string.
        """
        slug = slugify(base)
        queryset = Product.objects.all()
        if instance:
            queryset = queryset.exclude(pk=instance.pk)
        candidate, n = slug, 1
        while queryset.filter(slug=candidate).exists():
            candidate = f"{slug}-{n}"
            n += 1
        return candidate

    def create(self, validated_data):
        """Auto-assign the vendor from request context and generate slug."""
        validated_data["vendor"] = self.context["request"].user.vendor_profile
        if not validated_data.get("slug"):
            validated_data["slug"] = self._unique_slug(validated_data["name"])
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Regenerate slug from updated name when slug is blank."""
        if not validated_data.get("slug"):
            validated_data["slug"] = self._unique_slug(
                validated_data.get("name", instance.name), instance
            )
        return super().update(instance, validated_data)
