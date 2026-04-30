from rest_framework import serializers
from django.utils.text import slugify

from products.models import (
    CatalogProduct,
    CatalogProductImage,
    CatalogProposal,
    CatalogProposalItem,
    Category,
    VendorCatalogGrant,
    Product,
)
from products.serializers.category_serializers import CategorySerializer


class CatalogProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogProductImage
        fields = ["id", "image", "is_primary", "display_order"]


class CatalogProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source="category",
        write_only=True,
        required=False,
        allow_null=True,
    )
    images = CatalogProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = CatalogProduct
        fields = [
            "id",
            "category",
            "category_id",
            "name",
            "slug",
            "description",
            "brand",
            "unit",
            "barcode",
            "search_keywords",
            "compliance_notes",
            "is_active",
            "images",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {"slug": {"required": False, "allow_blank": True}}

    def _unique_slug(self, name, instance=None):
        base = slugify(name) or "catalog-product"
        qs = CatalogProduct.objects.all()
        if instance:
            qs = qs.exclude(pk=instance.pk)
        candidate = base
        n = 1
        while qs.filter(slug=candidate).exists():
            candidate = f"{base}-{n}"
            n += 1
        return candidate

    def create(self, validated_data):
        if not validated_data.get("slug"):
            validated_data["slug"] = self._unique_slug(validated_data["name"])
        request = self.context.get("request")
        if request:
            validated_data["created_by"] = request.user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if not validated_data.get("slug"):
            validated_data["slug"] = self._unique_slug(
                validated_data.get("name", instance.name),
                instance,
            )
        return super().update(instance, validated_data)


class VendorCatalogGrantSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.store_name", read_only=True)
    catalog_product = CatalogProductSerializer(read_only=True)

    class Meta:
        model = VendorCatalogGrant
        fields = ["id", "vendor", "vendor_name", "catalog_product", "granted_at"]


class CatalogProposalItemSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source="category",
        write_only=True,
        required=False,
        allow_null=True,
    )
    created_catalog_product = CatalogProductSerializer(read_only=True)

    class Meta:
        model = CatalogProposalItem
        fields = [
            "id",
            "name",
            "category",
            "category_id",
            "description",
            "brand",
            "unit",
            "barcode",
            "sku_hint",
            "status",
            "created_catalog_product",
            "rejection_reason",
            "reviewed_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "created_catalog_product",
            "rejection_reason",
            "reviewed_at",
        ]


class CatalogProposalSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.store_name", read_only=True)
    items = CatalogProposalItemSerializer(many=True)

    class Meta:
        model = CatalogProposal
        fields = [
            "id",
            "vendor",
            "vendor_name",
            "status",
            "submitted_at",
            "reviewed_by",
            "reviewed_at",
            "admin_notes",
            "items",
        ]
        read_only_fields = [
            "id",
            "vendor",
            "vendor_name",
            "status",
            "submitted_at",
            "reviewed_by",
            "reviewed_at",
            "admin_notes",
        ]

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required.")
        for item in value:
            if not item.get("name"):
                raise serializers.ValidationError("Each item requires a name.")
        return value


class CatalogProposalReviewSerializer(serializers.Serializer):
    catalog_product_id = serializers.UUIDField(required=False)
    rejection_reason = serializers.CharField(required=False, allow_blank=True)
    admin_notes = serializers.CharField(required=False, allow_blank=True)


class CreateVendorProductFromCatalogSerializer(serializers.Serializer):
    catalog_product_id = serializers.UUIDField()
    brand = serializers.CharField(required=False, allow_blank=True, max_length=120)
    unit = serializers.CharField(required=False, allow_blank=True, max_length=20)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    compare_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    tax_rate = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, default=0)
    sku = serializers.CharField(required=False, allow_blank=True, max_length=50)
    stock = serializers.IntegerField(required=False, default=0, min_value=0)
    low_stock_threshold = serializers.IntegerField(required=False, default=10, min_value=0)
    min_order_quantity = serializers.IntegerField(required=False, default=1, min_value=1)
    weight = serializers.CharField(required=False, allow_blank=True, max_length=50)
    is_available = serializers.BooleanField(required=False, default=True)
    prep_time_minutes = serializers.IntegerField(required=False, default=0, min_value=0)
    is_instant_delivery = serializers.BooleanField(required=False, default=True)
    is_scheduled_delivery = serializers.BooleanField(required=False, default=True)
    is_perishable = serializers.BooleanField(required=False, default=False)
    requires_cold_storage = serializers.BooleanField(required=False, default=False)
    is_fragile = serializers.BooleanField(required=False, default=False)
    is_age_restricted = serializers.BooleanField(required=False, default=False)
    allow_customer_notes = serializers.BooleanField(required=False, default=True)
    is_returnable = serializers.BooleanField(required=False, default=True)
    packaging_instructions = serializers.CharField(required=False, allow_blank=True)
    ingredients = serializers.CharField(required=False, allow_blank=True)
    allergens = serializers.CharField(required=False, allow_blank=True, max_length=255)
    shelf_life = serializers.CharField(required=False, allow_blank=True, max_length=100)
    status = serializers.ChoiceField(required=False, default="active", choices=["active", "draft", "sold_out", "coming_soon", "archived"])
    is_featured = serializers.BooleanField(required=False, default=False)
    inheritance_mode = serializers.ChoiceField(
        required=False,
        choices=[
            Product.INHERITANCE_MODE_BASE_IMAGE,
            Product.INHERITANCE_MODE_VENDOR_IMAGE_ONLY,
            Product.INHERITANCE_MODE_MIXED,
        ],
        default=Product.INHERITANCE_MODE_BASE_IMAGE,
    )


class InheritedProductDraftBatchSerializer(serializers.Serializer):
    catalog_product_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
    )


class InheritedProductSubmitSerializer(serializers.Serializer):
    product_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
    )


class InheritedProductImagePolicySerializer(serializers.Serializer):
    inheritance_mode = serializers.ChoiceField(
        choices=[
            Product.INHERITANCE_MODE_BASE_IMAGE,
            Product.INHERITANCE_MODE_VENDOR_IMAGE_ONLY,
            Product.INHERITANCE_MODE_MIXED,
        ]
    )


class AdminVendorProductRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True, allow_blank=False)
