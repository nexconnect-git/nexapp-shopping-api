from rest_framework import serializers
from vendors.models import VendorAuditLog, VendorReview

class VendorAuditLogSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField(read_only=True)
    action_label = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = VendorAuditLog
        fields = [
            "id", "action", "action_label", "description",
            "performed_by_name", "ip_address", "metadata", "created_at",
        ]

    def get_performed_by_name(self, obj) -> str:
        if obj.performed_by:
            return (f"{obj.performed_by.first_name} {obj.performed_by.last_name}".strip() or obj.performed_by.username)
        return "System"


class VendorReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.get_full_name", read_only=True)

    class Meta:
        model = VendorReview
        fields = ["id", "vendor", "customer", "customer_name", "rating", "comment", "created_at"]
        read_only_fields = ["id", "customer", "created_at"]

    def create(self, validated_data):
        validated_data["customer"] = self.context["request"].user
        return super().create(validated_data)
