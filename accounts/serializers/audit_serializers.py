from rest_framework import serializers

from accounts.models import AdminAuditLog


class AdminAuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.username', read_only=True)
    actor_email = serializers.EmailField(source='actor.email', read_only=True)

    class Meta:
        model = AdminAuditLog
        fields = [
            'id',
            'actor',
            'actor_name',
            'actor_email',
            'action',
            'entity_type',
            'entity_id',
            'summary',
            'metadata',
            'ip_address',
            'user_agent',
            'created_at',
        ]
        read_only_fields = fields
