import uuid
from django.db import models
from vendors.models import Vendor
from products.models.catalog import CatalogProduct
from products.models.category import Category


class Product(models.Model):
    INHERITANCE_MODE_BASE_IMAGE = "base_image"
    INHERITANCE_MODE_VENDOR_IMAGE_ONLY = "vendor_image_only"
    INHERITANCE_MODE_MIXED = "mixed"
    INHERITANCE_MODE_CHOICES = (
        (INHERITANCE_MODE_BASE_IMAGE, "Use Base Image"),
        (INHERITANCE_MODE_VENDOR_IMAGE_ONLY, "Use Vendor Image Only"),
        (INHERITANCE_MODE_MIXED, "Use Base + Vendor Images"),
    )

    APPROVAL_STATUS_DRAFT = "draft"
    APPROVAL_STATUS_PENDING = "pending_approval"
    APPROVAL_STATUS_APPROVED = "approved"
    APPROVAL_STATUS_REJECTED = "rejected"
    APPROVAL_STATUS_CHOICES = (
        (APPROVAL_STATUS_DRAFT, "Draft"),
        (APPROVAL_STATUS_PENDING, "Pending Approval"),
        (APPROVAL_STATUS_APPROVED, "Approved"),
        (APPROVAL_STATUS_REJECTED, "Rejected"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='products')
    catalog_product = models.ForeignKey(
        CatalogProduct,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='vendor_products',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='products',
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField()
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    brand = models.CharField(max_length=120, blank=True)
    sku = models.CharField(max_length=50, blank=True)
    stock = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=10)
    min_order_quantity = models.PositiveIntegerField(default=1)
    unit = models.CharField(max_length=20, default='piece')
    weight = models.CharField(max_length=50, blank=True)
    is_available = models.BooleanField(default=True)
    prep_time_minutes = models.PositiveIntegerField(default=0)
    is_instant_delivery = models.BooleanField(default=True)
    is_scheduled_delivery = models.BooleanField(default=True)
    is_perishable = models.BooleanField(default=False)
    requires_cold_storage = models.BooleanField(default=False)
    is_fragile = models.BooleanField(default=False)
    is_age_restricted = models.BooleanField(default=False)
    allow_customer_notes = models.BooleanField(default=True)
    is_returnable = models.BooleanField(default=True)
    packaging_instructions = models.TextField(blank=True)
    search_keywords = models.CharField(max_length=255, blank=True)
    ingredients = models.TextField(blank=True)
    allergens = models.CharField(max_length=255, blank=True)
    shelf_life = models.CharField(max_length=100, blank=True)
    barcode = models.CharField(max_length=100, blank=True)
    compliance_notes = models.TextField(blank=True)

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('draft', 'Draft'),
        ('sold_out', 'Sold Out'),
        ('coming_soon', 'Coming Soon'),
        ('archived', 'Archived'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    is_featured = models.BooleanField(default=False)
    inheritance_mode = models.CharField(
        max_length=20,
        choices=INHERITANCE_MODE_CHOICES,
        default=INHERITANCE_MODE_BASE_IMAGE,
    )
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default=APPROVAL_STATUS_DRAFT,
    )
    rejection_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_vendor_products",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approval_requested_at = models.DateTimeField(null=True, blank=True)
    approval_change_summary = models.JSONField(default=list, blank=True)
    submission_batch_id = models.UUIDField(null=True, blank=True)
    brand_normalized = models.CharField(max_length=120, blank=True)
    quantity_normalized = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    unit_normalized = models.CharField(max_length=30, blank=True)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_ratings = models.IntegerField(default=0)
    total_orders = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'products'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "vendor",
                    "catalog_product",
                    "brand_normalized",
                    "quantity_normalized",
                    "unit_normalized",
                ],
                name="uniq_vendor_catalog_variant_signature",
            )
        ]

    def __str__(self):
        return self.name

    @property
    def discount_percentage(self):
        if self.compare_price and self.compare_price > self.price:
            return round(((self.compare_price - self.price) / self.compare_price) * 100)
        return 0

    @property
    def in_stock(self):
        if not self.is_available:
            return False
        return self.stock > 0
