import uuid
from django.db import models
from accounts.models import User


class OrderIssue(models.Model):
    ISSUE_TYPE_CHOICES = [
        ('return', 'Return Request'),
        ('refund', 'Refund Request'),
        ('damage', 'Damaged Item'),
        ('mismatch', 'Item Mismatch'),
    ]
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_review', 'In Review'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
        ('refund_initiated', 'Refund Initiated'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='issues')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='order_issues')
    issue_type = models.CharField(max_length=20, choices=ISSUE_TYPE_CHOICES)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    # Admin resolution fields
    admin_notes = models.TextField(blank=True)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    refund_method = models.CharField(max_length=100, blank=True)
    resolved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_issues'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orders'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_issue_type_display()} — {self.order.order_number}"


class IssueMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue = models.ForeignKey(OrderIssue, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='issue_messages')
    is_admin = models.BooleanField(default=False)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'orders'
        ordering = ['created_at']

    def __str__(self):
        return f"Message on issue {self.issue_id} by {self.sender.username}"
