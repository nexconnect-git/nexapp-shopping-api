import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class AdminPermissionGrant(models.Model):
    PERMISSION_CHOICES = (
        ('dispatch.manage', 'Manage dispatch'),
        ('orders.manage', 'Manage orders'),
        ('catalog.manage', 'Manage catalog'),
        ('vendors.manage', 'Manage vendors'),
        ('customers.manage', 'Manage customers'),
        ('support.manage', 'Manage support'),
        ('finance.manage', 'Manage finance'),
        ('settings.manage', 'Manage platform settings'),
        ('audit.view', 'View audit logs'),
        ('notifications.manage', 'Manage notifications'),
        ('automation.manage', 'Manage scheduled tasks'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='admin_permission_grants',
    )
    permission = models.CharField(max_length=80, choices=PERMISSION_CHOICES)
    scope = models.JSONField(default=dict, blank=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='granted_admin_permissions',
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = 'accounts'
        ordering = ['user__username', 'permission']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'permission'],
                name='unique_admin_permission_grant',
            ),
        ]

    def __str__(self):
        return f'{self.user.username}: {self.permission}'
