from rest_framework import serializers
from notifications.models import DeviceToken


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['id', 'token', 'platform', 'created_at']
        read_only_fields = ['id', 'created_at']
