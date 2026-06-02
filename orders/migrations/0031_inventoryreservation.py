from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0030_cartitem_price_at_add_orderitem_snapshots"),
        ("products", "0013_product_prod_vendor_visible_idx_and_more"),
        ("vendors", "0013_vendor_vendor_public_area_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryReservation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.PositiveIntegerField()),
                ("price_at_reservation", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("reserved", "Reserved"),
                            ("committed", "Committed"),
                            ("released", "Released"),
                            ("expired", "Expired"),
                        ],
                        default="reserved",
                        max_length=20,
                    ),
                ),
                ("reserved_until", models.DateTimeField()),
                ("committed_at", models.DateTimeField(blank=True, null=True)),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "cart",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="inventory_reservations",
                        to="orders.cart",
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inventory_reservations",
                        to="orders.order",
                    ),
                ),
                (
                    "order_item",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inventory_reservation",
                        to="orders.orderitem",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="inventory_reservations",
                        to="products.product",
                    ),
                ),
                (
                    "vendor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="inventory_reservations",
                        to="vendors.vendor",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["product", "status"], name="invres_product_status_idx"),
                    models.Index(fields=["vendor", "status"], name="invres_vendor_status_idx"),
                    models.Index(fields=["status", "reserved_until"], name="invres_status_until_idx"),
                    models.Index(fields=["order", "status"], name="invres_order_status_idx"),
                ],
            },
        ),
    ]
