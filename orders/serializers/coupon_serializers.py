"""Serializers for coupon-related models."""

from rest_framework import serializers

from orders.models import Coupon


class CouponSerializer(serializers.ModelSerializer):
    """Serializer for coupon codes, including vendor name for display."""

    vendor_name = serializers.CharField(
        source="vendor.store_name", read_only=True, allow_null=True
    )

    class Meta:
        model = Coupon
        fields = [
            "id", "code", "title", "description", "discount_type", "discount_value",
            "min_order_amount", "max_discount_amount", "vendor", "vendor_name",
            "is_active", "usage_limit", "per_user_limit", "used_count",
            "valid_from", "valid_until", "created_at",
        ]
        read_only_fields = ["id", "used_count", "created_at", "vendor_name"]
