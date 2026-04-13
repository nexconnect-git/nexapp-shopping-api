from rest_framework import serializers

from delivery.models import DeliveryEarning


class DeliveryEarningSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)

    class Meta:
        model = DeliveryEarning
        fields = ['id', 'delivery_partner', 'order', 'order_number', 'amount', 'created_at']
        read_only_fields = ['id', 'created_at']
