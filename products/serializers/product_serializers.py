from rest_framework import serializers
from django.utils.text import slugify

from products.models import Product
from products.serializers.catalog_serializers import CatalogProductSerializer
from products.serializers.category_serializers import CategorySerializer
from products.serializers.image_serializers import ProductImageSerializer
from vendors.serializers import VendorListSerializer


class ProductSerializer(serializers.ModelSerializer):
    """Full product serializer with nested vendor, category, and images."""

    images = ProductImageSerializer(many=True, read_only=True)
    catalog_product = CatalogProductSerializer(read_only=True)
    vendor = VendorListSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True)
    in_stock = serializers.BooleanField(read_only=True)
    image_count = serializers.SerializerMethodField()
    visibility_status = serializers.SerializerMethodField()
    visibility_blockers = serializers.SerializerMethodField()
    category_visibility = serializers.SerializerMethodField()
    sales_count = serializers.SerializerMethodField()
    revenue = serializers.SerializerMethodField()
    requires_admin_review = serializers.SerializerMethodField()
    approval_status_label = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "vendor", "category", "name", "slug", "description",
            "catalog_product",
            "price", "compare_price", "tax_rate", "brand", "sku", "stock",
            "low_stock_threshold", "min_order_quantity", "unit", "weight",
            "is_available", "prep_time_minutes", "is_instant_delivery",
            "is_scheduled_delivery", "is_perishable", "requires_cold_storage",
            "is_fragile", "is_age_restricted", "allow_customer_notes",
            "is_returnable", "packaging_instructions", "search_keywords",
            "ingredients", "allergens", "shelf_life", "barcode",
            "compliance_notes", "status", "is_featured", "inheritance_mode",
            "approval_status", "approval_status_label", "rejection_reason", "reviewed_at",
            "approval_requested_at", "approval_change_summary", "requires_admin_review",
            "submission_batch_id", "average_rating",
            "total_ratings", "total_orders", "discount_percentage", "in_stock",
            "images", "image_count", "visibility_status", "visibility_blockers",
            "category_visibility", "sales_count", "revenue", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "average_rating", "total_ratings", "total_orders",
            "created_at", "updated_at",
        ]

    def get_image_count(self, obj) -> int:
        annotated = getattr(obj, "image_count", None)
        if annotated is not None:
            return annotated
        count = obj.images.count()
        if count == 0 and obj.catalog_product_id:
            return obj.catalog_product.images.count()
        return count

    def get_category_visibility(self, obj) -> str:
        if not obj.category:
            return "missing"
        return "customer_visible" if obj.category.show_in_customer_ui else "pending_review"

    def get_visibility_blockers(self, obj) -> list[str]:
        blockers = []
        if obj.status != "active":
            blockers.append("Product status is not active.")
        if not obj.is_available:
            blockers.append("Product is marked unavailable.")
        if obj.stock <= 0:
            blockers.append("Product is out of stock.")
        if self.get_image_count(obj) == 0:
            blockers.append("Add at least one product image.")
        if not obj.category:
            blockers.append("Select a category.")
        elif not obj.category.show_in_customer_ui:
            blockers.append("Category is awaiting customer-app approval.")
        return blockers

    def get_visibility_status(self, obj) -> str:
        return "ready_to_sell" if not self.get_visibility_blockers(obj) else "needs_attention"

    def get_sales_count(self, obj) -> int:
        return getattr(obj, "sales_count", None) or obj.total_orders or 0

    def get_revenue(self, obj):
        return getattr(obj, "revenue", 0) or 0

    def get_requires_admin_review(self, obj) -> bool:
        return obj.approval_status == Product.APPROVAL_STATUS_PENDING

    def get_approval_status_label(self, obj) -> str:
        return dict(Product.APPROVAL_STATUS_CHOICES).get(obj.approval_status, obj.approval_status)


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight product serializer for list views (no nested reviews)."""

    primary_image = serializers.SerializerMethodField()
    catalog_product = CatalogProductSerializer(read_only=True)
    vendor_name = serializers.CharField(source="vendor.store_name", read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True)
    in_stock = serializers.BooleanField(read_only=True)
    image_count = serializers.SerializerMethodField()
    visibility_status = serializers.SerializerMethodField()
    visibility_blockers = serializers.SerializerMethodField()
    category_visibility = serializers.SerializerMethodField()
    sales_count = serializers.SerializerMethodField()
    revenue = serializers.SerializerMethodField()
    requires_admin_review = serializers.SerializerMethodField()
    approval_status_label = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "vendor", "name", "slug", "description", "price",
            "catalog_product",
            "compare_price", "tax_rate", "brand", "unit", "stock",
            "low_stock_threshold", "min_order_quantity", "weight",
            "prep_time_minutes", "is_instant_delivery", "is_scheduled_delivery",
            "is_perishable", "requires_cold_storage", "is_fragile",
            "is_age_restricted", "allow_customer_notes", "is_returnable",
            "packaging_instructions", "search_keywords", "ingredients",
            "allergens", "shelf_life", "barcode", "compliance_notes",
            "is_available", "status", "is_featured", "inheritance_mode",
            "approval_status", "approval_status_label", "rejection_reason", "reviewed_at",
            "approval_requested_at", "approval_change_summary", "requires_admin_review", "submission_batch_id",
            "average_rating", "total_ratings", "discount_percentage", "in_stock",
            "primary_image", "vendor_name", "image_count", "visibility_status",
            "visibility_blockers", "category_visibility", "sales_count", "revenue",
        ]

    def get_primary_image(self, obj) -> str | None:
        """Return the absolute URL of the primary image, or None."""
        primary = obj.images.filter(is_primary=True).first()
        if primary:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(primary.image.url)
            return primary.image.url
        if obj.catalog_product_id:
            catalog_primary = obj.catalog_product.images.filter(is_primary=True).first()
            if not catalog_primary:
                catalog_primary = obj.catalog_product.images.first()
            if catalog_primary:
                request = self.context.get("request")
                if request:
                    return request.build_absolute_uri(catalog_primary.image.url)
                return catalog_primary.image.url
        return None

    def get_image_count(self, obj) -> int:
        annotated = getattr(obj, "image_count", None)
        if annotated is not None:
            return annotated
        count = obj.images.count()
        if count == 0 and obj.catalog_product_id:
            return obj.catalog_product.images.count()
        return count

    def get_category_visibility(self, obj) -> str:
        if not obj.category:
            return "missing"
        return "customer_visible" if obj.category.show_in_customer_ui else "pending_review"

    def get_visibility_blockers(self, obj) -> list[str]:
        blockers = []
        if obj.status != "active":
            blockers.append("Product status is not active.")
        if not obj.is_available:
            blockers.append("Product is marked unavailable.")
        if obj.stock <= 0:
            blockers.append("Product is out of stock.")
        if self.get_image_count(obj) == 0:
            blockers.append("Add at least one product image.")
        if not obj.category:
            blockers.append("Select a category.")
        elif not obj.category.show_in_customer_ui:
            blockers.append("Category is awaiting customer-app approval.")
        return blockers

    def get_visibility_status(self, obj) -> str:
        return "ready_to_sell" if not self.get_visibility_blockers(obj) else "needs_attention"

    def get_sales_count(self, obj) -> int:
        return getattr(obj, "sales_count", None) or obj.total_orders or 0

    def get_revenue(self, obj):
        return getattr(obj, "revenue", 0) or 0

    def get_requires_admin_review(self, obj) -> bool:
        return obj.approval_status == Product.APPROVAL_STATUS_PENDING

    def get_approval_status_label(self, obj) -> str:
        return dict(Product.APPROVAL_STATUS_CHOICES).get(obj.approval_status, obj.approval_status)


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Write serializer for vendor product creation and updates.

    Auto-generates a unique slug from the product name when none is supplied.
    """

    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "category", "name", "slug", "description", "price",
            "compare_price", "tax_rate", "brand", "sku", "stock",
            "low_stock_threshold", "min_order_quantity", "unit", "weight",
            "is_available", "prep_time_minutes", "is_instant_delivery",
            "is_scheduled_delivery", "is_perishable", "requires_cold_storage",
            "is_fragile", "is_age_restricted", "allow_customer_notes",
            "is_returnable", "packaging_instructions", "search_keywords",
            "ingredients", "allergens", "shelf_life", "barcode",
            "compliance_notes", "status", "is_featured", "inheritance_mode",
            "images",
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
        if not validated_data.get("catalog_product"):
            raise serializers.ValidationError({
                "catalog_product": "Products must be added from an approved catalog item."
            })
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
