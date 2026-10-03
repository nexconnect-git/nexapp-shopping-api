from django.utils import timezone
from rest_framework import serializers

from helpers.validators import validate_document_upload
from vendors.models import Vendor, VendorDocument
from vendors.serializers.public import VendorSerializer


class OwnerVendorProfileSerializer(VendorSerializer):
    class Meta(VendorSerializer.Meta):
        fields = [
            'store_name', 'description', 'logo', 'banner', 'phone', 'email',
            'address', 'city', 'state', 'postal_code', 'latitude', 'longitude',
            'opening_time', 'closing_time', 'min_order_amount', 'base_prep_time_min',
            'delivery_radius_km', 'instant_delivery_radius_km', 'packaging_preferences',
            'cancellation_rules', 'auto_order_acceptance',
        ]
        read_only_fields = []
        extra_kwargs = {'latitude': {'allow_null': False}, 'longitude': {'allow_null': False}}

    def to_internal_value(self, data):
        forbidden = set(data) - set(self.Meta.fields)
        if forbidden:
            raise serializers.ValidationError({key: 'This field cannot be changed through store profile.' for key in forbidden})
        return super().to_internal_value(data)

    def validate(self, attrs):
        current = self.instance
        value = lambda key: attrs.get(key, getattr(current, key, None))
        latitude, longitude = value('latitude'), value('longitude')
        if latitude is not None and not -90 <= latitude <= 90:
            raise serializers.ValidationError({'latitude': 'Use a latitude between -90 and 90.'})
        if longitude is not None and not -180 <= longitude <= 180:
            raise serializers.ValidationError({'longitude': 'Use a longitude between -180 and 180.'})
        for key in ('min_order_amount', 'base_prep_time_min', 'delivery_radius_km', 'instant_delivery_radius_km'):
            if value(key) is not None and value(key) < 0:
                raise serializers.ValidationError({key: 'Use a non-negative value.'})
        if value('instant_delivery_radius_km') > value('delivery_radius_km'):
            raise serializers.ValidationError({'instant_delivery_radius_km': 'Instant radius cannot exceed the delivery radius.'})
        if value('delivery_radius_km') > current.max_delivery_radius_km:
            raise serializers.ValidationError({'delivery_radius_km': 'Delivery radius exceeds your configured maximum.'})
        return attrs


class VendorOperatingCommandSerializer(serializers.Serializer):
    is_open = serializers.BooleanField(required=False)
    is_accepting_orders = serializers.BooleanField(required=False)
    closing_time = serializers.TimeField(required=False)

    def validate(self, attrs):
        if not attrs or set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError('Provide supported operating fields only.')
        return attrs


class InventoryReviewSerializer(serializers.Serializer):
    confirmed = serializers.BooleanField()
    product_count = serializers.IntegerField(min_value=0)
    updated_at = serializers.DateTimeField(allow_null=True)


class OnboardingDocumentUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorDocument
        fields = ['document_type', 'file']

    def validate_file(self, value):
        try:
            validate_document_upload(value, label='vendor document')
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value
