import uuid
from django.db import models
from accounts.models import User
from vendors.models import Vendor

TICKET_CATEGORY_CHOICES = (
    ('billing',   'Billing & Payments'),
    ('technical', 'Technical Issue'),
    ('order',     'Order Issue'),
    ('account',   'Account Issue'),
    ('other',     'Other'),
)

TICKET_STATUS_CHOICES = (
    ('open',        'Open'),
    ('in_progress', 'In Progress'),
    ('resolved',    'Resolved'),
    ('closed',      'Closed'),
)

TICKET_PRIORITY_CHOICES = (
    ('low',    'Low'),
    ('medium', 'Medium'),
    ('high',   'High'),
)


class SupportTicket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='support_tickets')
    subject = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=TICKET_CATEGORY_CHOICES, default='other')
    priority = models.CharField(max_length=10, choices=TICKET_PRIORITY_CHOICES, default='medium')
    message = models.TextField()
    status = models.CharField(max_length=20, choices=TICKET_STATUS_CHOICES, default='open')
    admin_response = models.TextField(blank=True)
    responded_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='support_responses'
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'support'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_status_display()}] {self.subject} — {self.vendor.store_name}'
