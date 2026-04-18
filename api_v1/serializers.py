from rest_framework import serializers
from vendors.models import Vendor


class VendorV1Serializer(serializers.ModelSerializer):
    distance_km = serializers.FloatField(read_only=True, default=None)
    eta_min = serializers.IntegerField(read_only=True, default=None)
    delivery_type = serializers.CharField(read_only=True, default=None)

    class Meta:
        model = Vendor
        fields = [
            "id", "store_name", "logo", "city", "state",
            "is_open", "is_accepting_orders",
            "average_rating", "total_ratings",
            "delivery_radius_km", "instant_delivery_radius_km", "max_delivery_radius_km",
            "base_prep_time_min", "delivery_time_per_km_min", "scheduled_buffer_min",
            "min_order_amount", "is_featured", "vendor_type", "vendor_tier",
            "latitude", "longitude",
            "distance_km", "eta_min", "delivery_type",
        ]
