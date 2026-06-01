from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from delivery.models import DeliveryAssignment
from helpers.geo_helpers import calculate_eta_minutes, haversine


class DeliveryAssignmentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    vendor_name = serializers.CharField(source='order.vendor.store_name', read_only=True)
    vendor_lat = serializers.DecimalField(
        source='order.vendor.latitude', max_digits=9, decimal_places=6, read_only=True
    )
    vendor_lng = serializers.DecimalField(
        source='order.vendor.longitude', max_digits=9, decimal_places=6, read_only=True
    )
    vendor_address = serializers.CharField(source='order.vendor.address', read_only=True)
    order_total = serializers.DecimalField(
        source='order.total', max_digits=10, decimal_places=2, read_only=True
    )
    order_items = serializers.SerializerMethodField()
    expires_at = serializers.SerializerMethodField()
    seconds_remaining = serializers.SerializerMethodField()
    pickup_distance_km = serializers.SerializerMethodField()
    drop_distance_km = serializers.SerializerMethodField()
    estimated_eta_minutes = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryAssignment
        fields = [
            'id', 'status', 'current_radius_km',
            'order', 'order_number', 'vendor_name', 'vendor_lat', 'vendor_lng',
            'vendor_address', 'order_total', 'order_items',
            'expires_at', 'seconds_remaining',
            'pickup_distance_km', 'drop_distance_km', 'estimated_eta_minutes',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_order_items(self, obj):
        return [
            {
                'name': item.product_name,
                'quantity': item.quantity,
                'price': str(item.product_price),
            }
            for item in obj.order.items.all()
        ]

    def get_expires_at(self, obj):
        return obj.last_search_at + timedelta(minutes=1)

    def get_seconds_remaining(self, obj):
        expires_at = self.get_expires_at(obj)
        remaining = int((expires_at - timezone.now()).total_seconds())
        return max(0, remaining)

    def _distance_context(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        partner = getattr(user, 'delivery_profile', None)
        if not partner:
            return None

        partner_lat = float(partner.current_latitude or 0)
        partner_lng = float(partner.current_longitude or 0)
        vendor_lat = float(obj.order.vendor.latitude or 0)
        vendor_lng = float(obj.order.vendor.longitude or 0)
        customer_lat = float(obj.order.delivery_latitude or 0)
        customer_lng = float(obj.order.delivery_longitude or 0)

        if not (partner_lat and partner_lng and vendor_lat and vendor_lng):
            return None

        pickup_distance_km = round(
            haversine(partner_lat, partner_lng, vendor_lat, vendor_lng),
            2,
        )
        drop_distance_km = (
            round(haversine(vendor_lat, vendor_lng, customer_lat, customer_lng), 2)
            if customer_lat and customer_lng
            else None
        )
        estimated_eta_minutes = (
            calculate_eta_minutes(
                partner_lat,
                partner_lng,
                vendor_lat,
                vendor_lng,
                customer_lat,
                customer_lng,
            )
            if customer_lat and customer_lng
            else None
        )

        return {
            'pickup_distance_km': pickup_distance_km,
            'drop_distance_km': drop_distance_km,
            'estimated_eta_minutes': estimated_eta_minutes,
        }

    def get_pickup_distance_km(self, obj):
        data = self._distance_context(obj)
        return data['pickup_distance_km'] if data else None

    def get_drop_distance_km(self, obj):
        data = self._distance_context(obj)
        return data['drop_distance_km'] if data else None

    def get_estimated_eta_minutes(self, obj):
        data = self._distance_context(obj)
        return data['estimated_eta_minutes'] if data else None
