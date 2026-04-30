from rest_framework import serializers

from orders.models import DeliveryZone, FeatureFlag, RefundLedger, TaxRule


class RefundLedgerSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    customer_name = serializers.CharField(source='customer.username', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.username', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True)
    processed_by_name = serializers.CharField(source='processed_by.username', read_only=True)

    class Meta:
        model = RefundLedger
        fields = [
            'id',
            'order',
            'order_number',
            'issue',
            'customer',
            'customer_name',
            'amount',
            'method',
            'status',
            'reason',
            'gateway_refund_id',
            'failure_reason',
            'requested_by',
            'requested_by_name',
            'approved_by',
            'approved_by_name',
            'processed_by',
            'processed_by_name',
            'requested_at',
            'approved_at',
            'processed_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'requested_by',
            'approved_by',
            'processed_by',
            'requested_at',
            'approved_at',
            'processed_at',
            'created_at',
            'updated_at',
        ]


class DeliveryZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryZone
        fields = [
            'id',
            'name',
            'city',
            'country',
            'center_latitude',
            'center_longitude',
            'radius_km',
            'is_active',
            'instant_delivery_enabled',
            'scheduled_delivery_enabled',
            'base_fee_override',
            'per_km_fee_override',
            'surge_multiplier',
            'min_order_value',
            'max_delivery_distance_km',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TaxRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxRule
        fields = [
            'id',
            'name',
            'country',
            'region',
            'tax_rate',
            'applies_to',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FeatureFlagSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)

    class Meta:
        model = FeatureFlag
        fields = [
            'key',
            'name',
            'description',
            'is_enabled',
            'audience',
            'rollout_percentage',
            'metadata',
            'updated_by',
            'updated_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['updated_by', 'updated_by_name', 'created_at', 'updated_at']
