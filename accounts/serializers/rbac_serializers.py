from rest_framework import serializers

from accounts.models import AdminPermissionGrant


class AdminPermissionGrantSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    granted_by_name = serializers.CharField(source='granted_by.username', read_only=True)

    class Meta:
        model = AdminPermissionGrant
        fields = [
            'id',
            'user',
            'user_name',
            'user_email',
            'permission',
            'scope',
            'granted_by',
            'granted_by_name',
            'created_at',
        ]
        read_only_fields = ['id', 'granted_by', 'granted_by_name', 'created_at']
