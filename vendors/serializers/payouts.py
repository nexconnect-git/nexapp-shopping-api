from rest_framework import serializers
from vendors.models import VendorPayout, DeliveryPartnerPayout

class VendorPayoutSerializer(serializers.ModelSerializer):
    vendor_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = VendorPayout
        fields = "__all__"

    def get_vendor_name(self, obj) -> str:
        try:
            return obj.vendor.store_name
        except Exception:
            return str(obj.vendor_id)


class DeliveryPartnerPayoutSerializer(serializers.ModelSerializer):
    partner_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DeliveryPartnerPayout
        fields = "__all__"

    def get_partner_name(self, obj) -> str:
        try:
            user = obj.delivery_partner
            full_name = f"{user.first_name} {user.last_name}".strip()
            return full_name or user.username
        except Exception:
            return str(obj.delivery_partner_id)
