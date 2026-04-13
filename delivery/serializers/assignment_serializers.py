from rest_framework import serializers

from delivery.models import DeliveryAssignment


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

    class Meta:
        model = DeliveryAssignment
        fields = [
            'id', 'status', 'current_radius_km',
            'order', 'order_number', 'vendor_name', 'vendor_lat', 'vendor_lng',
            'vendor_address', 'order_total', 'order_items',
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
