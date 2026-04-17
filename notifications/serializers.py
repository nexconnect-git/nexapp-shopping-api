from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'notification_type', 'is_read',
                  'data', 'created_at']
        read_only_fields = ['id', 'title', 'message', 'notification_type',
                            'data', 'created_at']


class AdminNotificationSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'user', 'username', 'title', 'message',
                  'notification_type', 'is_read', 'data', 'created_at']
        read_only_fields = ['id', 'created_at']


class SendNotificationSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False, help_text='Omit to broadcast')
    role = serializers.ChoiceField(
        choices=['customer', 'vendor', 'delivery', 'admin'],
        required=False,
        help_text='Filter broadcast by role. Ignored when user_id is set.',
    )
    title = serializers.CharField(max_length=200)
    message = serializers.CharField()
    notification_type = serializers.ChoiceField(
        choices=Notification.TYPE_CHOICES, default='system'
    )
