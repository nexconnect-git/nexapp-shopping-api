import uuid
from django.db import models
from accounts.models import User
from helpers.upload_paths import UserDateUploadPath


class OrderIssue(models.Model):
    ISSUE_TYPE_CHOICES = [
        ('return', 'Return Request'),
        ('refund', 'Refund Request'),
        ('damage', 'Damaged Item'),
        ('mismatch', 'Item Mismatch'),
        ('late', 'Late Delivery'),
    ]
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_review', 'In Review'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
        ('refund_initiated', 'Refund Initiated'),
        ('assigned', 'Assigned'), ('investigating', 'Investigating'),
        ('waiting_customer', 'Waiting for customer'), ('waiting_vendor', 'Waiting for vendor'),
        ('waiting_partner', 'Waiting for partner'), ('resolution_pending', 'Resolution pending'),
        ('closed', 'Closed'), ('escalated', 'Escalated'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='issues')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='order_issues')
    issue_type = models.CharField(max_length=20, choices=ISSUE_TYPE_CHOICES)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    # Admin resolution fields
    admin_notes = models.TextField(blank=True)
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_support_cases')
    queue = models.CharField(max_length=60, blank=True, default='support')
    priority = models.CharField(max_length=12, choices=(('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')), default='normal')
    due_at = models.DateTimeField(null=True, blank=True)
    resolution_type = models.CharField(max_length=20, choices=(('', 'None'), ('refund', 'Refund review'), ('replacement', 'Replacement review'), ('compensation', 'Compensation review'), ('explanation', 'Explanation')), blank=True)
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


class OrderIssueAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue = models.ForeignKey(OrderIssue, on_delete=models.CASCADE, related_name='attachments')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='issue_attachments')
    file = models.FileField(upload_to=UserDateUploadPath('order_attachment'))
    content_type = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'orders'
        ordering = ['created_at']

    def __str__(self):
        return f"Attachment on issue {self.issue_id} by {self.uploaded_by.username}"
