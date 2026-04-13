from rest_framework import serializers
from delivery.models.asset import Asset

class AssetSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = ['id', 'name', 'asset_type', 'serial_number', 'description',
                  'status', 'assigned_to', 'assigned_to_name', 'purchase_date',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.user.get_full_name() or obj.assigned_to.user.username
        return None
