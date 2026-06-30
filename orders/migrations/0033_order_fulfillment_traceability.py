from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0016_fulfillment_nodes"),
        ("orders", "0032_cart_fulfillment_lock"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="fulfillment_node",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="orders", to="vendors.fulfillmentnode"),
        ),
        migrations.AddField(
            model_name="order",
            name="fulfillment_promise_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="fulfillment_promise_id",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="fulfillment_node",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_item_snapshots", to="vendors.fulfillmentnode"),
        ),
        migrations.AddField(
            model_name="inventoryreservation",
            name="fulfillment_node",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="inventory_reservations", to="vendors.fulfillmentnode"),
        ),
    ]
