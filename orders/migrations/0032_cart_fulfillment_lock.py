from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0016_fulfillment_nodes"),
        ("orders", "0031_inventoryreservation"),
    ]

    operations = [
        migrations.AddField(
            model_name="cart",
            name="fulfillment_locked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cart",
            name="fulfillment_node",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="carts", to="vendors.fulfillmentnode"),
        ),
        migrations.AddField(
            model_name="cart",
            name="fulfillment_promise_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cart",
            name="fulfillment_promise_id",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
    ]
