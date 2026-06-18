from django.contrib.auth import get_user_model
from rest_framework import serializers
from accounts.data.user_repository import UserRepository
from helpers.media_helpers import safe_media_url
from helpers.phone_helpers import normalize_phone
from helpers.serializer_fields import SafeImageField
from helpers.vendor_hours import get_vendor_availability, is_vendor_open_now
from products.models import Product
from products.data.product_repository import ProductRepository
from products.serializers.category_serializers import CategorySerializer
from vendors.models import Vendor, VENDOR_TYPE_CHOICES

User = get_user_model()

class VendorSerializer(serializers.ModelSerializer):
    logo = SafeImageField(required=False, allow_null=True)
    banner = SafeImageField(required=False, allow_null=True)
    user_info = serializers.SerializerMethodField()
    is_open_now = serializers.SerializerMethodField()
    availability_note = serializers.SerializerMethodField()

    class Meta:
        model = Vendor
        fields = [
            "id", "user_info", "store_name", "description", "logo", "banner",
            "phone", "email", "address", "city", "state", "postal_code",
            "latitude", "longitude",
            "vendor_type", "vendor_tier",
            "status", "status_reason", "is_open", "is_open_now", "availability_note", "opening_time", "closing_time", "is_accepting_orders",
            "operating_hours",
            "min_order_amount", "delivery_radius_km",
            "instant_delivery_radius_km", "max_delivery_radius_km",
            "base_prep_time_min", "delivery_time_per_km_min", "scheduled_buffer_min",
            "fulfillment_type", "dispatch_sla_hours", "return_policy",
            "packaging_preferences", "auto_order_acceptance", "cancellation_rules",
            "average_rating", "total_ratings", "is_featured",
            "require_stock_check", "wallet_balance",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "status_reason", "average_rating", "total_ratings",
            "is_featured", "wallet_balance", "created_at", "updated_at",
        ]

    def get_user_info(self, obj) -> dict:
        request = self.context.get("request")
        avatar = safe_media_url(obj.user.avatar, request=request)
        data = {
            "id": str(obj.user.id),
            "username": obj.user.username,
            "email": obj.user.email,
            "first_name": obj.user.first_name,
            "last_name": obj.user.last_name,
            "phone": obj.user.phone,
            "avatar": avatar,
            "country": obj.user.country,
            "currency": obj.user.currency,
            "role": obj.user.role,
            "is_staff": obj.user.is_staff,
            "is_superuser": obj.user.is_superuser,
            "is_active": obj.user.is_active,
            "is_verified": obj.user.is_verified,
            "force_password_change": obj.user.force_password_change,
            "date_joined": obj.user.date_joined,
            "last_login": obj.user.last_login,
            "created_at": obj.user.created_at,
            "updated_at": obj.user.updated_at,
        }
        if obj.user.force_password_change and obj.user.temp_password:
            data["temp_password"] = obj.user.temp_password
        return data

    def get_is_open_now(self, obj) -> bool:
        return is_vendor_open_now(obj)

    def get_availability_note(self, obj) -> str:
        return get_vendor_availability(obj)[1]


class VendorListProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    primary_image = serializers.SerializerMethodField()
    vendor_name = serializers.CharField(source="vendor.store_name", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "category", "name", "slug", "description", "price",
            "compare_price", "brand", "unit", "stock", "weight",
            "average_rating", "total_ratings", "primary_image", "vendor_name",
        ]

    def get_primary_image(self, obj) -> str | None:
        primary = obj.images.filter(is_primary=True).first() or obj.images.first()
        if not primary and obj.catalog_product_id:
            primary = obj.catalog_product.images.filter(is_primary=True).first() or obj.catalog_product.images.first()
        if not primary:
            return None
        return safe_media_url(primary.image, request=self.context.get("request"))


class VendorListSerializer(serializers.ModelSerializer):
    logo = SafeImageField(read_only=True)
    is_open_now = serializers.SerializerMethodField()
    availability_note = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()
    distance_km = serializers.FloatField(read_only=True, required=False)
    estimated_delivery_minutes = serializers.IntegerField(read_only=True, required=False)
    matched_products_preview = serializers.ListField(child=serializers.CharField(), read_only=True)
    has_previously_ordered = serializers.BooleanField(read_only=True, default=False)
    within_instant_radius = serializers.BooleanField(read_only=True, default=False)
    far_order_eta_label = serializers.CharField(read_only=True, default="")
    estimated_delivery_label = serializers.CharField(read_only=True, default="")
    vehicle_type = serializers.CharField(read_only=True, default="")
    vehicle_reason = serializers.CharField(read_only=True, default="")
    is_far_delivery = serializers.BooleanField(read_only=True, default=False)
    requires_far_delivery_confirmation = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Vendor
        fields = [
            "id", "store_name", "logo", "city", "state", "is_open", "is_open_now", "availability_note", "is_accepting_orders",
            "average_rating", "total_ratings", "delivery_radius_km",
            "instant_delivery_radius_km", "max_delivery_radius_km",
            "base_prep_time_min", "delivery_time_per_km_min", "scheduled_buffer_min",
            "min_order_amount", "is_featured", "vendor_type", "vendor_tier",
            "latitude", "longitude",
            "distance_km", "estimated_delivery_minutes", "estimated_delivery_label",
            "far_order_eta_label", "vehicle_type", "vehicle_reason",
            "is_far_delivery", "requires_far_delivery_confirmation",
            "within_instant_radius", "matched_products_preview", "has_previously_ordered",
            "products",
        ]

    def get_is_open_now(self, obj) -> bool:
        return is_vendor_open_now(obj)

    def get_availability_note(self, obj) -> str:
        return get_vendor_availability(obj)[1]

    def get_products(self, obj) -> list[dict]:
        products = getattr(obj, "available_products", None)
        if products is None:
            products = (
                obj.products.filter(
                    **ProductRepository.customer_visible_filter(),
                )
                .select_related("category", "catalog_product")
                .prefetch_related("images", "catalog_product__images")
                .order_by("category__display_order", "category__name", "name")
            )
        return VendorListProductSerializer(products, many=True, context=self.context).data

class VendorRegistrationSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=False, default="")
    last_name = serializers.CharField(required=False, default="")
    store_name = serializers.CharField(max_length=200)
    vendor_type = serializers.ChoiceField(
        choices=[choice[0] for choice in VENDOR_TYPE_CHOICES],
        default="retail_store",
    )
    description = serializers.CharField(required=False, default="")
    phone = serializers.CharField(max_length=30)
    vendor_email = serializers.EmailField()
    address = serializers.CharField(max_length=255)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    postal_code = serializers.CharField(max_length=10)
    latitude = serializers.DecimalField(max_digits=11, decimal_places=8)
    longitude = serializers.DecimalField(max_digits=11, decimal_places=8)
    logo = serializers.ImageField(required=False, allow_null=True)
    banner = serializers.ImageField(required=False, allow_null=True)

    def validate_username(self, value: str) -> str:
        value = value.strip()
        if UserRepository.username_exists(value):
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if UserRepository.email_exists(value, role="vendor"):
            raise serializers.ValidationError("Email already exists for a vendor account.")
        return value

    def validate_phone(self, value: str) -> str:
        try:
            phone = normalize_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        if UserRepository.phone_exists(phone, role="vendor"):
            raise serializers.ValidationError("Phone number already exists for a vendor account.")
        return phone

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            phone=validated_data["phone"],
            role="vendor",
        )
        return Vendor.objects.create(
            user=user,
            store_name=validated_data["store_name"],
            vendor_type=validated_data.get("vendor_type", "retail_store"),
            description=validated_data.get("description", ""),
            phone=validated_data["phone"],
            email=validated_data["vendor_email"],
            address=validated_data["address"],
            city=validated_data["city"],
            state=validated_data["state"],
            postal_code=validated_data["postal_code"],
            latitude=validated_data["latitude"],
            longitude=validated_data["longitude"],
            logo=validated_data.get("logo"),
            banner=validated_data.get("banner"),
        )
