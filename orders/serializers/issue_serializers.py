"""Serializers for order issue models."""

from rest_framework import serializers
from orders.models import IssueMessage, OrderIssue


class IssueMessageSerializer(serializers.ModelSerializer):
    """Serializer for a message thread entry on an order issue."""

    sender_name = serializers.CharField(source="sender.get_full_name", read_only=True)
    sender_username = serializers.CharField(source="sender.username", read_only=True)

    class Meta:
        model = IssueMessage
        fields = [
            "id", "sender", "sender_name", "sender_username",
            "is_admin", "message", "created_at",
        ]
        read_only_fields = [
            "id", "sender", "sender_name", "sender_username", "is_admin", "created_at",
        ]


class OrderIssueSerializer(serializers.ModelSerializer):
    """Full serializer for an order issue with nested message thread."""

    messages = IssueMessageSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.get_full_name", read_only=True)
    customer_username = serializers.CharField(source="customer.username", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    issue_type_display = serializers.CharField(source="get_issue_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = OrderIssue
        fields = [
            "id", "order", "order_number", "customer", "customer_name", "customer_username",
            "issue_type", "issue_type_display", "description", "status", "status_display",
            "admin_notes", "refund_amount", "refund_method", "resolved_by", "resolved_at",
            "created_at", "updated_at", "messages",
        ]
        read_only_fields = [
            "id", "customer", "customer_name", "customer_username", "order_number",
            "issue_type_display", "status_display", "resolved_by", "resolved_at",
            "created_at", "updated_at",
        ]
