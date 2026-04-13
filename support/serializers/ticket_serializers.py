from rest_framework import serializers
from support.models import SupportTicket


class SupportTicketSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.store_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = SupportTicket
        fields = [
            'id', 'vendor', 'vendor_name', 'subject', 'category', 'category_display',
            'priority', 'message', 'status', 'status_display',
            'admin_response', 'responded_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'vendor', 'vendor_name', 'admin_response',
            'responded_at', 'created_at', 'updated_at',
        ]
