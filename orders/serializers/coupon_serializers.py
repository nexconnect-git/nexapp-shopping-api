"""Serializers for coupon-related models."""

from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import serializers

from orders.models import Coupon, CouponUsage


class CouponSerializer(serializers.ModelSerializer):
    """Serializer for coupon codes, including vendor name for display."""

    vendor_name = serializers.CharField(
        source="vendor.store_name", read_only=True, allow_null=True
    )
    usage_count = serializers.IntegerField(source="used_count", read_only=True)
    revenue_influenced = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    health_warnings = serializers.SerializerMethodField()

    class Meta:
        model = Coupon
        fields = [
            "id", "code", "title", "description", "discount_type", "discount_value",
            "min_order_amount", "max_discount_amount", "vendor", "vendor_name",
            "is_active", "usage_limit", "per_user_limit", "used_count",
            "usage_count", "revenue_influenced", "is_expired", "status_label",
            "health_warnings", "valid_from", "valid_until", "created_at",
        ]
        read_only_fields = ["id", "used_count", "created_at", "vendor_name"]

    def get_revenue_influenced(self, obj):
        return CouponUsage.objects.filter(coupon=obj).aggregate(
            total=Coalesce(Sum("order__total"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))
        )["total"]

    def get_is_expired(self, obj) -> bool:
        return bool(obj.valid_until and obj.valid_until < timezone.now())

    def get_status_label(self, obj) -> str:
        now = timezone.now()
        if not obj.is_active:
            return "Inactive"
        if obj.valid_from > now:
            return "Upcoming"
        if obj.valid_until and obj.valid_until < now:
            return "Expired"
        if obj.usage_limit and obj.used_count >= obj.usage_limit:
            return "Limit reached"
        return "Active"

    def get_health_warnings(self, obj) -> list[str]:
        warnings = []
        now = timezone.now()
        if not obj.is_active:
            warnings.append("Coupon is inactive.")
        if obj.valid_until and obj.valid_until < now:
            warnings.append("Coupon has expired.")
        if obj.valid_until and obj.valid_until <= obj.valid_from:
            warnings.append("End date must be after start date.")
        if obj.usage_limit and obj.used_count >= obj.usage_limit:
            warnings.append("Usage limit has been reached.")
        if obj.min_order_amount and obj.min_order_amount <= 0:
            warnings.append("No minimum order is set.")
        return warnings
