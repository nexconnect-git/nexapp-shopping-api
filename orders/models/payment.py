import uuid

from django.conf import settings
from django.db import models


class PaymentSession(models.Model):
    STATUS_CREATED = 'created'
    STATUS_PENDING = 'pending'
    STATUS_AUTHORIZED = 'authorized'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'
    STATUS_REFUNDED = 'refunded'
    STATUS_RECONCILED = 'reconciled'

    STATUS_CHOICES = (
        (STATUS_CREATED, 'Created'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_AUTHORIZED, 'Authorized'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_REFUNDED, 'Refunded'),
        (STATUS_RECONCILED, 'Reconciled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_sessions',
    )
    orders = models.ManyToManyField('orders.Order', blank=True, related_name='payment_sessions')
    gateway = models.CharField(max_length=40, default='razorpay')
    gateway_order_id = models.CharField(max_length=120, unique=True)
    gateway_payment_id = models.CharField(max_length=120, blank=True, default='', db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='INR')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CREATED)
    metadata = models.JSONField(default=dict, blank=True)
    last_event_id = models.CharField(max_length=120, blank=True, default='')
    mismatch_reason = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status', 'created_at'], name='orders_paym_custome_236582_idx'),
            models.Index(fields=['gateway_order_id', 'status'], name='orders_paym_gateway_d9553e_idx'),
        ]

    def __str__(self):
        return f'{self.gateway}:{self.gateway_order_id} [{self.status}]'
