import uuid

from django.db import models


FULFILLMENT_NODE_TYPE_CHOICES = (
    ("vendor_store", "Vendor Store"),
    ("platform_dark_store", "Platform Dark Store"),
    ("hub", "Hub"),
)

FULFILLMENT_NODE_STATUS_CHOICES = (
    ("active", "Active"),
    ("paused", "Paused"),
    ("maintenance", "Maintenance"),
    ("disabled", "Disabled"),
)


class FulfillmentNode(models.Model):
    """Physical or virtual stock origin used for customer promises."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(
        "vendors.Vendor",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="fulfillment_nodes",
    )
    code = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=200)
    node_type = models.CharField(
        max_length=30,
        choices=FULFILLMENT_NODE_TYPE_CHOICES,
        default="vendor_store",
    )
    status = models.CharField(
        max_length=20,
        choices=FULFILLMENT_NODE_STATUS_CHOICES,
        default="active",
    )
    is_accepting_orders = models.BooleanField(default=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=10, blank=True)
    latitude = models.DecimalField(max_digits=11, decimal_places=8, default=0)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, default=0)
    instant_radius_km = models.DecimalField(max_digits=5, decimal_places=2, default=2.5)
    max_delivery_radius_km = models.DecimalField(max_digits=5, decimal_places=2, default=5.0)
    base_prep_time_min = models.PositiveIntegerField(default=10)
    delivery_time_per_km_min = models.DecimalField(max_digits=4, decimal_places=2, default=3.0)
    daily_order_capacity = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "vendors"
        indexes = [
            models.Index(fields=["status", "is_accepting_orders", "city", "state"], name="ff_node_area_idx"),
            models.Index(fields=["vendor", "status"], name="ff_node_vendor_status_idx"),
            models.Index(fields=["node_type", "status"], name="ff_node_type_status_idx"),
        ]

    def __str__(self):
        return self.name

    @property
    def is_active_for_customers(self) -> bool:
        return self.status == "active" and self.is_accepting_orders


class FulfillmentNodeServiceArea(models.Model):
    """Optional tighter service area for a fulfillment node."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    node = models.ForeignKey(
        FulfillmentNode,
        on_delete=models.CASCADE,
        related_name="service_areas",
    )
    label = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=10, blank=True)
    center_latitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    center_longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    radius_km = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "vendors"
        ordering = ["priority", "created_at"]
        indexes = [
            models.Index(fields=["node", "is_active", "priority"], name="ff_area_node_active_idx"),
            models.Index(fields=["city", "state", "postal_code"], name="ff_area_location_idx"),
        ]

    def __str__(self):
        return self.label or f"{self.node} service area"


class FulfillmentNodeInventory(models.Model):
    """Node-level sellable stock for a product."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    node = models.ForeignKey(
        FulfillmentNode,
        on_delete=models.CASCADE,
        related_name="inventory_items",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="fulfillment_inventory",
    )
    stock = models.IntegerField(default=0)
    reserved_stock = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=5)
    is_available = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "vendors"
        constraints = [
            models.UniqueConstraint(fields=["node", "product"], name="uniq_node_product_inventory"),
        ]
        indexes = [
            models.Index(fields=["node", "is_available", "stock"], name="ff_inv_node_stock_idx"),
            models.Index(fields=["product", "is_available"], name="ff_inv_product_available_idx"),
        ]

    @property
    def sellable_stock(self) -> int:
        return max(0, int(self.stock or 0) - int(self.reserved_stock or 0))

    def __str__(self):
        return f"{self.product_id} at {self.node_id}"
