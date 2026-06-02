import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone

from products.models import Product
from vendors.models import Vendor


class InventoryReservation(models.Model):
    """Ledger record for direct-store stock reserved during checkout."""

    STATUS_RESERVED = "reserved"
    STATUS_COMMITTED = "committed"
    STATUS_RELEASED = "released"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = (
        (STATUS_RESERVED, "Reserved"),
        (STATUS_COMMITTED, "Committed"),
        (STATUS_RELEASED, "Released"),
        (STATUS_EXPIRED, "Expired"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(
        "orders.Cart",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_reservations",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="inventory_reservations",
    )
    order_item = models.OneToOneField(
        "orders.OrderItem",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="inventory_reservation",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="inventory_reservations",
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="inventory_reservations",
    )
    quantity = models.PositiveIntegerField()
    price_at_reservation = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RESERVED)
    reserved_until = models.DateTimeField()
    committed_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "orders"
        indexes = [
            models.Index(fields=["product", "status"], name="invres_product_status_idx"),
            models.Index(fields=["vendor", "status"], name="invres_vendor_status_idx"),
            models.Index(fields=["status", "reserved_until"], name="invres_status_until_idx"),
            models.Index(fields=["order", "status"], name="invres_order_status_idx"),
        ]

    @classmethod
    def default_expiry(cls):
        return timezone.now() + timedelta(minutes=15)

    def commit(self):
        self.status = self.STATUS_COMMITTED
        self.committed_at = timezone.now()
        self.released_at = None
        self.save(update_fields=["status", "committed_at", "released_at", "updated_at"])

    def release(self):
        self.status = self.STATUS_RELEASED
        self.released_at = timezone.now()
        self.save(update_fields=["status", "released_at", "updated_at"])

    def __str__(self):
        return f"{self.quantity} reserved for {self.product_id} [{self.status}]"
