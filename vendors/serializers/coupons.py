from rest_framework import serializers

from orders.serializers.coupon_serializers import CouponSerializer


class VendorCouponSerializer(CouponSerializer):
    class Meta(CouponSerializer.Meta):
        read_only_fields = CouponSerializer.Meta.read_only_fields + ['vendor', 'usage_count', 'revenue_influenced', 'is_expired', 'status_label', 'health_warnings']

    def validate_code(self, value):
        value = value.strip().upper()
        if not 3 <= len(value) <= 50 or any(not (character.isascii() and (character.isalnum() or character in '-_')) for character in value):
            raise serializers.ValidationError('Use 3–50 letters, numbers, dashes or underscores.')
        return value

    def validate(self, values):
        current = self.instance
        value = lambda key: values.get(key, getattr(current, key, None))
        kind, discount = value('discount_type') or 'percentage', value('discount_value')
        if discount is not None and (discount < 0 or (kind != 'free_delivery' and discount <= 0) or (kind == 'percentage' and discount > 100)):
            raise serializers.ValidationError({'discount_value': 'Enter a positive discount; percentages cannot exceed 100.'})
        for key in ('min_order_amount', 'max_discount_amount'):
            if value(key) is not None and value(key) < 0:
                raise serializers.ValidationError({key: 'Use a non-negative amount.'})
        for key in ('usage_limit', 'per_user_limit'):
            if value(key) is not None and (isinstance(self.initial_data.get(key), bool) or value(key) < 1):
                raise serializers.ValidationError({key: 'Use a whole number of at least 1.'})
        if value('valid_from') and value('valid_until') and value('valid_until') <= value('valid_from'):
            raise serializers.ValidationError({'valid_until': 'End date must be after start date.'})
        return values
