from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.data.user_repository import UserRepository
from delivery.models import DeliveryPartner
from helpers.phone_helpers import normalize_phone

User = get_user_model()


class DeliveryPartnerSerializer(serializers.ModelSerializer):
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
        avatar = obj.user.avatar.url if obj.user.avatar else None
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

    def update(self, instance, validated_data):
        """Forward admin-edit user fields from request data to the related User model."""
        request = self.context.get('request')
        if request:
            user_updated = []
            if 'user_is_active' in request.data:
                val = request.data['user_is_active']
                if isinstance(val, str):
                    val = val.lower() == 'true'
                instance.user.is_active = bool(val)
                user_updated.append('is_active')
            for field in ['username', 'first_name', 'last_name', 'email', 'phone', 'country', 'currency']:
                if field in request.data:
                    setattr(instance.user, field, request.data[field])
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

    def validate_username(self, value):
        value = value.strip()
        if UserRepository.username_exists(value):
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if UserRepository.email_exists(value):
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate_phone(self, value):
        if not value:
            return ''
        try:
            phone = normalize_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        if UserRepository.phone_exists(phone):
            raise serializers.ValidationError("Phone number already exists.")
        return phone

    def create(self, validated_data):
        password = validated_data.get('password')
        auto_generated_password = None
        if not password:
            auto_generated_password = User.objects.make_random_password()
            password = auto_generated_password

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=password,
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone=validated_data.get('phone', ''),
            role='delivery',
        )
        if auto_generated_password:
            user.force_password_change = True
            user.save(update_fields=['force_password_change'])

        partner = DeliveryPartner.objects.create(
            user=user,
            vehicle_type=validated_data['vehicle_type'],
            vehicle_number=validated_data.get('vehicle_number', ''),
            license_number=validated_data['license_number'],
        )
        if auto_generated_password:
            partner.auto_generated_password = auto_generated_password
        return partner


class UpdateLocationSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
