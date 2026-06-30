import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0013_product_prod_vendor_visible_idx_and_more"),
        ("vendors", "0015_vendor_status_reason_and_statuses"),
    ]

    operations = [
        migrations.CreateModel(
            name="FulfillmentNode",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=200)),
                ("node_type", models.CharField(choices=[("vendor_store", "Vendor Store"), ("platform_dark_store", "Platform Dark Store"), ("hub", "Hub")], default="vendor_store", max_length=30)),
                ("status", models.CharField(choices=[("active", "Active"), ("paused", "Paused"), ("maintenance", "Maintenance"), ("disabled", "Disabled")], default="active", max_length=20)),
                ("is_accepting_orders", models.BooleanField(default=True)),
                ("address", models.CharField(blank=True, max_length=255)),
                ("city", models.CharField(blank=True, max_length=100)),
                ("state", models.CharField(blank=True, max_length=100)),
                ("postal_code", models.CharField(blank=True, max_length=10)),
                ("latitude", models.DecimalField(decimal_places=8, default=0, max_digits=11)),
                ("longitude", models.DecimalField(decimal_places=8, default=0, max_digits=11)),
                ("instant_radius_km", models.DecimalField(decimal_places=2, default=2.5, max_digits=5)),
                ("max_delivery_radius_km", models.DecimalField(decimal_places=2, default=5.0, max_digits=5)),
                ("base_prep_time_min", models.PositiveIntegerField(default=10)),
                ("delivery_time_per_km_min", models.DecimalField(decimal_places=2, default=3.0, max_digits=4)),
                ("daily_order_capacity", models.PositiveIntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("vendor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="fulfillment_nodes", to="vendors.vendor")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["status", "is_accepting_orders", "city", "state"], name="ff_node_area_idx"),
                    models.Index(fields=["vendor", "status"], name="ff_node_vendor_status_idx"),
                    models.Index(fields=["node_type", "status"], name="ff_node_type_status_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="FulfillmentNodeServiceArea",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("label", models.CharField(blank=True, max_length=120)),
                ("city", models.CharField(blank=True, max_length=100)),
                ("state", models.CharField(blank=True, max_length=100)),
                ("postal_code", models.CharField(blank=True, max_length=10)),
                ("center_latitude", models.DecimalField(blank=True, decimal_places=8, max_digits=11, null=True)),
                ("center_longitude", models.DecimalField(blank=True, decimal_places=8, max_digits=11, null=True)),
                ("radius_km", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("is_active", models.BooleanField(default=True)),
                ("priority", models.PositiveIntegerField(default=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("node", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="service_areas", to="vendors.fulfillmentnode")),
            ],
            options={
                "ordering": ["priority", "created_at"],
                "indexes": [
                    models.Index(fields=["node", "is_active", "priority"], name="ff_area_node_active_idx"),
                    models.Index(fields=["city", "state", "postal_code"], name="ff_area_location_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="FulfillmentNodeInventory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("stock", models.IntegerField(default=0)),
                ("reserved_stock", models.IntegerField(default=0)),
                ("low_stock_threshold", models.IntegerField(default=5)),
                ("is_available", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("node", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="inventory_items", to="vendors.fulfillmentnode")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fulfillment_inventory", to="products.product")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["node", "is_available", "stock"], name="ff_inv_node_stock_idx"),
                    models.Index(fields=["product", "is_available"], name="ff_inv_product_available_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("node", "product"), name="uniq_node_product_inventory"),
                ],
            },
        ),
    ]
