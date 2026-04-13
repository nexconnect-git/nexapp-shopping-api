from rest_framework import serializers

from accounts.models.address import Address


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'label', 'full_name', 'phone', 'address_line1', 'address_line2',
                  'city', 'state', 'postal_code', 'latitude', 'longitude', 'is_default',
                  'created_at']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
