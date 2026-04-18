import uuid
from django.db import models
from accounts.models import User

VENDOR_TYPE_CHOICES = (
    ('individual', 'Individual'),
    ('company', 'Company'),
    ('partnership', 'Partnership'),
)

FULFILLMENT_TYPE_CHOICES = (
    ('vendor', 'Vendor Fulfilled'),
    ('platform', 'Platform Fulfilled'),
)

VENDOR_TIER_CHOICES = (
    ('basic', 'Basic'),
    ('silver', 'Silver'),
    ('gold', 'Gold'),
    ('platinum', 'Platinum'),
)


class Vendor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    STATUS_CHOICES = (
        ('pending',   'Pending Approval'),
        ('approved',  'Approved'),
        ('rejected',  'Rejected'),
        ('suspended', 'Suspended'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor_profile')

    # ── Core store info ───────────────────────────────────────────────────────
    store_name   = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    logo         = models.ImageField(upload_to='vendor_logos/',   blank=True, null=True)
    banner       = models.ImageField(upload_to='vendor_banners/', blank=True, null=True)
    phone        = models.CharField(max_length=15)
    email        = models.EmailField()
    address      = models.CharField(max_length=255)
    city         = models.CharField(max_length=100)
    state        = models.CharField(max_length=100)
    postal_code  = models.CharField(max_length=10)
    latitude     = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    longitude    = models.DecimalField(max_digits=9, decimal_places=6, default=0)

    # ── Classification ────────────────────────────────────────────────────────
    vendor_type  = models.CharField(max_length=20, choices=VENDOR_TYPE_CHOICES, default='individual', blank=True)
    vendor_tier  = models.CharField(max_length=20, choices=VENDOR_TIER_CHOICES, default='basic', blank=True)

    # ── Approval / ratings ────────────────────────────────────────────────────
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_featured    = models.BooleanField(default=False)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_ratings  = models.IntegerField(default=0)
    wallet_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ── Operating hours ───────────────────────────────────────────────────────
    is_open       = models.BooleanField(default=True)
    opening_time  = models.TimeField(default='09:00')
    closing_time  = models.TimeField(default='22:00')

    # ── Delivery settings ─────────────────────────────────────────────────────
    min_order_amount           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_radius_km         = models.DecimalField(max_digits=5,  decimal_places=2, default=5.0)

    # ── Delivery quote engine ─────────────────────────────────────────────────
    instant_delivery_radius_km = models.DecimalField(max_digits=5,  decimal_places=2, default=2.5)
    max_delivery_radius_km     = models.DecimalField(max_digits=5,  decimal_places=2, default=5.0)
    base_prep_time_min         = models.IntegerField(default=15)
    delivery_time_per_km_min   = models.DecimalField(max_digits=4,  decimal_places=2, default=3.0)
    scheduled_buffer_min       = models.IntegerField(default=30)
    is_accepting_orders        = models.BooleanField(default=True)
    operating_hours            = models.JSONField(default=dict, blank=True)

    # ── Fulfillment ───────────────────────────────────────────────────────────
    fulfillment_type         = models.CharField(max_length=20, choices=FULFILLMENT_TYPE_CHOICES, default='vendor', blank=True)
    dispatch_sla_hours       = models.IntegerField(default=24)
    return_policy            = models.TextField(blank=True)
    packaging_preferences    = models.TextField(blank=True)
    auto_order_acceptance    = models.BooleanField(default=False)
    cancellation_rules       = models.TextField(blank=True)

    # ── Stock check gate (admin-controlled) ───────────────────────────────────
    require_stock_check      = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'vendors'

    def __str__(self):
        return self.store_name
