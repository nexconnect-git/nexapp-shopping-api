import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class RefundLedger(models.Model):
    STATUS_CHOICES = (
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )
    METHOD_CHOICES = (
        ('wallet', 'Wallet'),
        ('razorpay', 'Razorpay'),
        ('manual', 'Manual'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='refund_ledger')
    issue = models.ForeignKey(
        'orders.OrderIssue',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refund_ledger',
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refund_ledger',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='wallet')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='requested')
    reason = models.TextField(blank=True)
    gateway_refund_id = models.CharField(max_length=100, blank=True)
    failure_reason = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requested_refunds',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_refunds',
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_refunds',
    )
    requested_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orders'
        ordering = ['-created_at']

    def __str__(self):
        return f"Refund {self.amount} for {self.order.order_number}"


class DeliveryZone(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    city = models.CharField(max_length=120)
    country = models.CharField(max_length=2, default='IN')
    center_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    center_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    radius_km = models.DecimalField(max_digits=6, decimal_places=2)
    is_active = models.BooleanField(default=True)
    instant_delivery_enabled = models.BooleanField(default=True)
    scheduled_delivery_enabled = models.BooleanField(default=True)
    base_fee_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    per_km_fee_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    surge_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_delivery_distance_km = models.DecimalField(max_digits=6, decimal_places=2, default=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orders'
        ordering = ['city', 'name']

    def __str__(self):
        return f"{self.name} ({self.city})"


class TaxRule(models.Model):
    APPLIES_TO_CHOICES = (
        ('products', 'Products'),
        ('delivery_fee', 'Delivery Fee'),
        ('platform_fee', 'Platform Fee'),
        ('all', 'All'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    country = models.CharField(max_length=2, default='IN')
    region = models.CharField(max_length=120, blank=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)
    applies_to = models.CharField(max_length=30, choices=APPLIES_TO_CHOICES, default='products')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orders'
        ordering = ['country', 'region', 'name']

    def __str__(self):
        return f"{self.name} - {self.tax_rate}%"


class FeatureFlag(models.Model):
    AUDIENCE_CHOICES = (
        ('all', 'All'),
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
        ('delivery', 'Delivery'),
        ('admin', 'Admin'),
    )

    key = models.SlugField(max_length=80, primary_key=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=False)
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default='all')
    rollout_percentage = models.PositiveSmallIntegerField(
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    metadata = models.JSONField(default=dict, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_feature_flags',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orders'
        ordering = ['key']

    def __str__(self):
        return self.key
