from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, default='customer')

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'first_name', 'last_name',
                  'phone', 'role']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'phone', 'avatar', 'role', 'country', 'is_verified', 'is_active',
                  'force_password_change', 'is_superuser', 'created_at', 'updated_at']
        read_only_fields = ['id', 'username', 'role', 'is_verified', 'is_active',
                            'force_password_change', 'is_superuser', 'created_at', 'updated_at']


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Admin-only serializer that allows changing is_active and is_verified."""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'is_verified', 'is_active']


class AdminUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    account_type = serializers.ChoiceField(
        choices=[('admin', 'Admin'), ('superuser', 'Superuser')],
        write_only=True,
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'first_name', 'last_name',
                  'phone', 'role', 'is_staff', 'is_superuser', 'created_at', 'account_type']
        read_only_fields = ['id', 'role', 'is_staff', 'is_superuser', 'created_at']

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
