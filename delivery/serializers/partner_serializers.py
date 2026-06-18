from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from rest_framework import serializers

from accounts.data.user_repository import UserRepository
from helpers.media_helpers import safe_media_url
from delivery.models import DeliveryPartner
from helpers.phone_helpers import normalize_phone
from helpers.serializer_fields import SafeFileField
from helpers.validators import validate_document_upload

User = get_user_model()


class DeliveryPartnerSerializer(serializers.ModelSerializer):
    id_proof = SafeFileField(required=False, allow_null=True)
    user = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryPartner
        fields = [
            'id', 'user', 'vehicle_type', 'vehicle_number', 'license_number',
            'id_proof', 'is_approved', 'is_available', 'status',
            'current_latitude', 'current_longitude', 'average_rating',
            'total_deliveries', 'total_earnings', 'wallet_balance',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'average_rating', 'total_deliveries',
            'total_earnings', 'wallet_balance', 'created_at', 'updated_at',
        ]

    def get_user(self, obj):
        avatar = safe_media_url(obj.user.avatar, request=self.context.get('request'))
        data = {
            'id': obj.user.id,
            'username': obj.user.username,
            'email': obj.user.email,
            'first_name': obj.user.first_name,
            'last_name': obj.user.last_name,
            'phone': obj.user.phone,
            'avatar': avatar,
            'country': obj.user.country,
            'currency': obj.user.currency,
            'role': obj.user.role,
            'is_staff': obj.user.is_staff,
            'is_superuser': obj.user.is_superuser,
            'is_active': obj.user.is_active,
            'is_verified': obj.user.is_verified,
            'force_password_change': obj.user.force_password_change,
            'date_joined': obj.user.date_joined,
            'last_login': obj.user.last_login,
            'created_at': obj.user.created_at,
            'updated_at': obj.user.updated_at,
        }
        if obj.user.force_password_change and obj.user.temp_password:
            data['temp_password'] = obj.user.temp_password
        return data

    def validate_id_proof(self, value):
        if value:
            try:
                validate_document_upload(value, label="delivery partner ID proof")
            except ValueError as exc:
                raise serializers.ValidationError(str(exc)) from exc
        return value

    def update(self, instance, validated_data):
        """Forward admin-edit user fields from request data to the related User model."""
        request = self.context.get('request')
        if request:
            user_updated = []
            if 'username' in request.data:
                username = str(request.data['username']).strip()
                if UserRepository.username_exists(username, exclude_user_id=instance.user_id):
                    raise serializers.ValidationError({'username': 'Username already exists.'})
            if 'email' in request.data:
                email = str(request.data['email']).strip().lower()
                if UserRepository.email_exists(email, exclude_user_id=instance.user_id, role='delivery'):
                    raise serializers.ValidationError({'email': 'Email already exists for a delivery account.'})
            if 'phone' in request.data:
                try:
                    phone = normalize_phone(str(request.data['phone']))
                except ValueError as exc:
                    raise serializers.ValidationError({'phone': str(exc)}) from exc
                if UserRepository.phone_exists(phone, exclude_user_id=instance.user_id, role='delivery'):
                    raise serializers.ValidationError({'phone': 'Phone number already exists for a delivery account.'})
            if 'user_is_active' in request.data:
                val = request.data['user_is_active']
                if isinstance(val, str):
                    val = val.lower() == 'true'
                instance.user.is_active = bool(val)
                user_updated.append('is_active')
            for field in ['username', 'first_name', 'last_name', 'email', 'phone', 'country', 'currency']:
                if field in request.data:
                    value = phone if field == 'phone' and 'phone' in request.data else request.data[field]
                    setattr(instance.user, field, value)
                    user_updated.append(field)
            if user_updated:
                instance.user.save(update_fields=list(set(user_updated)))
        return super().update(instance, validated_data)


class DeliveryPartnerRegistrationSerializer(serializers.Serializer):
    # User fields
    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, default='')
    last_name = serializers.CharField(required=False, default='')
    phone = serializers.CharField(max_length=30, required=False, default='')
    # Delivery partner fields
    vehicle_type = serializers.ChoiceField(choices=DeliveryPartner.VEHICLE_CHOICES)
    vehicle_number = serializers.CharField(max_length=20, required=False, default='')
    license_number = serializers.CharField(max_length=50)
    id_proof = serializers.FileField(required=False, allow_null=True)

    def validate_username(self, value):
        value = value.strip()
        if UserRepository.username_exists(value):
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if UserRepository.email_exists(value, role='delivery'):
            raise serializers.ValidationError("Email already exists for a delivery account.")
        return value

    def validate_phone(self, value):
        if not value:
            return ''
        try:
            phone = normalize_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        if UserRepository.phone_exists(phone, role='delivery'):
            raise serializers.ValidationError("Phone number already exists for a delivery account.")
        return phone

    def validate_id_proof(self, value):
        if not value:
            return value
        try:
            validate_document_upload(value, label="delivery partner ID proof")
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value

    def create(self, validated_data):
        password = validated_data.get('password')
        temporary_password = password
        auto_generated_password = None
        if not password:
            auto_generated_password = get_random_string(12)
            password = auto_generated_password
            temporary_password = auto_generated_password

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=password,
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone=validated_data.get('phone', ''),
            role='delivery',
        )
        user.force_password_change = True
        user.temp_password = temporary_password
        user.save(update_fields=['force_password_change', 'temp_password'])

        partner = DeliveryPartner.objects.create(
            user=user,
            vehicle_type=validated_data['vehicle_type'],
            vehicle_number=validated_data.get('vehicle_number', ''),
            license_number=validated_data['license_number'],
            id_proof=validated_data.get('id_proof'),
        )
        if auto_generated_password:
            partner.auto_generated_password = auto_generated_password
        return partner


class UpdateLocationSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    order_id = serializers.UUIDField(required=False)
