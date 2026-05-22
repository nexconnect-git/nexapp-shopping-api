from rest_framework import serializers
from django.contrib.auth import get_user_model
from accounts.data.user_repository import UserRepository
from helpers.phone_helpers import normalize_phone
from helpers.validators import validate_image_upload

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, default='customer')

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'first_name', 'last_name',
                  'phone', 'role']

    def validate_username(self, value: str) -> str:
        value = value.strip()
        if UserRepository.username_exists(value):
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if UserRepository.email_exists(value):
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate_phone(self, value: str) -> str:
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
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class MobileOTPRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField(required=False, allow_blank=True)


class MobileOTPVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    otp = serializers.CharField(min_length=6, max_length=6)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'phone', 'avatar', 'role', 'country', 'is_verified', 'is_active',
                  'force_password_change', 'is_superuser', 'created_at', 'updated_at']
        read_only_fields = ['id', 'username', 'role', 'is_verified', 'is_active',
                            'force_password_change', 'is_superuser', 'created_at', 'updated_at']

    def validate_avatar(self, value):
        if value:
            try:
                validate_image_upload(value, max_size_mb=3, label="avatar")
            except ValueError as exc:
                raise serializers.ValidationError(str(exc)) from exc
        return value


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Admin-only serializer that allows changing is_active and is_verified."""

    class Meta:
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'phone',
            'country',
            'is_verified',
            'is_active',
        ]


class AdminUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    account_type = serializers.ChoiceField(
        choices=[('admin', 'Admin'), ('superuser', 'Superuser')],
        write_only=True,
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'first_name', 'last_name',
                  'phone', 'avatar', 'country', 'role', 'is_staff', 'is_superuser',
                  'is_active', 'is_verified', 'force_password_change',
                  'date_joined', 'last_login', 'created_at', 'updated_at',
                  'account_type']
        read_only_fields = ['id', 'role', 'is_staff', 'is_superuser', 'is_active',
                            'is_verified', 'force_password_change', 'date_joined',
                            'last_login', 'created_at', 'updated_at']

    def validate_username(self, value: str) -> str:
        value = value.strip()
        if UserRepository.username_exists(value):
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if UserRepository.email_exists(value):
            raise serializers.ValidationError("Email already exists.")
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        account_type = validated_data.pop('account_type')
        user = User(**validated_data)
        user.set_password(password)

        user.role = 'admin'
        user.is_staff = True
        if account_type == 'superuser':
            user.is_superuser = True
        else:
            user.is_superuser = False

        user.save()
        return user
