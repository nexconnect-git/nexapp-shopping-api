from django.contrib.auth import get_user_model
from rest_framework import serializers
from helpers.vendor_hours import get_vendor_availability, is_vendor_open_now
from vendors.models import Vendor

User = get_user_model()

class VendorSerializer(serializers.ModelSerializer):
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
            "status", "is_open", "is_open_now", "availability_note", "opening_time", "closing_time", "is_accepting_orders",
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
            "id", "status", "average_rating", "total_ratings",
            "is_featured", "wallet_balance", "created_at", "updated_at",
        ]

    def get_user_info(self, obj) -> dict:
        data = {
            "id": str(obj.user.id),
            "username": obj.user.username,
            "email": obj.user.email,
            "first_name": obj.user.first_name,
            "last_name": obj.user.last_name,
            "phone": obj.user.phone,
            "force_password_change": obj.user.force_password_change,
        }
        if obj.user.force_password_change and obj.user.temp_password:
            data["temp_password"] = obj.user.temp_password
        return data

    def get_is_open_now(self, obj) -> bool:
        return is_vendor_open_now(obj)

    def get_availability_note(self, obj) -> str:
        return get_vendor_availability(obj)[1]

class VendorListSerializer(serializers.ModelSerializer):
    is_open_now = serializers.SerializerMethodField()
    availability_note = serializers.SerializerMethodField()
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
        ]

    def get_is_open_now(self, obj) -> bool:
        return is_vendor_open_now(obj)

    def get_availability_note(self, obj) -> str:
        return get_vendor_availability(obj)[1]

class VendorRegistrationSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=False, default="")
    last_name = serializers.CharField(required=False, default="")
    store_name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, default="")
    phone = serializers.CharField(max_length=15)
    vendor_email = serializers.EmailField()
    address = serializers.CharField(max_length=255)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    postal_code = serializers.CharField(max_length=10)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)

    def validate_username(self, value: str) -> str:
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            role="vendor",
        )
        return Vendor.objects.create(
            user=user,
            store_name=validated_data["store_name"],
            description=validated_data.get("description", ""),
            phone=validated_data["phone"],
            email=validated_data["vendor_email"],
            address=validated_data["address"],
            city=validated_data["city"],
            state=validated_data["state"],
            postal_code=validated_data["postal_code"],
            latitude=validated_data["latitude"],
            longitude=validated_data["longitude"],
        )
