import uuid

from django.conf import settings
from django.db import models

from products.models.category import Category
from vendors.models import Vendor


class CatalogProduct(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="catalog_products",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    brand = models.CharField(max_length=120, blank=True)
    unit = models.CharField(max_length=20, default="piece")
    barcode = models.CharField(max_length=100, blank=True)
    search_keywords = models.CharField(max_length=255, blank=True)
    compliance_notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_catalog_products",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "products"
        ordering = ["name"]

    def __str__(self):
        return self.name


class CatalogProductImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    catalog_product = models.ForeignKey(
        CatalogProduct,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="catalog-products/")
    is_primary = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)

    class Meta:
        app_label = "products"
        ordering = ["display_order"]


class VendorCatalogGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="catalog_grants")
    catalog_product = models.ForeignKey(
        CatalogProduct,
        on_delete=models.CASCADE,
        related_name="vendor_grants",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="catalog_grants_made",
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "products"
        unique_together = ("vendor", "catalog_product")
        ordering = ["-granted_at"]


class CatalogProposal(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("partially_approved", "Partially Approved"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="catalog_proposals")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="pending")
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_catalog_proposals",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)

    class Meta:
        app_label = "products"
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.vendor.store_name} catalog proposal"


class CatalogProposalItem(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal = models.ForeignKey(CatalogProposal, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    brand = models.CharField(max_length=120, blank=True)
    unit = models.CharField(max_length=20, default="piece")
    barcode = models.CharField(max_length=100, blank=True)
    sku_hint = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_catalog_product = models.ForeignKey(
        CatalogProduct,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proposal_items",
    )
    rejection_reason = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "products"
        ordering = ["name"]

    def __str__(self):
        return self.name
