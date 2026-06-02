from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0029_orderrating_split_fields"),
        ("products", "0013_product_prod_vendor_visible_idx_and_more"),
        ("vendors", "0013_vendor_vendor_public_area_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="cartitem",
            name="price_at_add",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="catalog_product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="order_item_snapshots",
                to="products.catalogproduct",
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="product_brand",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="product_compare_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="product_pack_size",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="product_sku",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="product_slug",
            field=models.SlugField(blank=True),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="product_unit",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="vendor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="order_item_snapshots",
                to="vendors.vendor",
            ),
        ),
    ]
