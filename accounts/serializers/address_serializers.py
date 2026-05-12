from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from accounts.models.address import Address


class CoordinateDecimalField(serializers.DecimalField):
    def to_internal_value(self, data):
        if data in (None, ''):
            return None
        try:
            data = Decimal(str(data)).quantize(Decimal('0.00000001'))
        except (InvalidOperation, TypeError, ValueError):
            self.fail('invalid')
        return super().to_internal_value(data)


class AddressSerializer(serializers.ModelSerializer):
    latitude = CoordinateDecimalField(max_digits=11, decimal_places=8, required=False, allow_null=True)
    longitude = CoordinateDecimalField(max_digits=11, decimal_places=8, required=False, allow_null=True)

    class Meta:
        model = Address
        fields = ['id', 'label', 'full_name', 'phone', 'address_line1', 'address_line2',
                  'landmark', 'city', 'state', 'postal_code', 'latitude', 'longitude',
                  'is_default', 'created_at']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
