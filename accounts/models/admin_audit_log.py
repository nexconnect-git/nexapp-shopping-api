import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class AdminAuditLog(models.Model):
    ACTION_CHOICES = (
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('status_change', 'Status Change'),
        ('payout', 'Payout'),
        ('settings', 'Settings'),
        ('notification', 'Notification'),
        ('login', 'Login'),
        ('other', 'Other'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_audit_logs',
    )
    action = models.CharField(max_length=32, choices=ACTION_CHOICES, default='other')
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100, blank=True)
    summary = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        app_label = 'accounts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['entity_type', 'entity_id']),
        ]

    def __str__(self):
        actor = self.actor.username if self.actor else 'system'
        return f'{actor} {self.action} {self.entity_type}:{self.entity_id}'
