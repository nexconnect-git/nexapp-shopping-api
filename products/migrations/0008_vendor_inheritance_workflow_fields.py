from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0007_catalogproduct_catalogproposal_catalogproposalitem_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="approval_status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("pending_approval", "Pending Approval"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                default="draft",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="brand_normalized",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="product",
            name="inheritance_mode",
            field=models.CharField(
                choices=[
                    ("base_image", "Use Base Image"),
                    ("vendor_image_only", "Use Vendor Image Only"),
                    ("mixed", "Use Base + Vendor Images"),
                ],
                default="base_image",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="quantity_normalized",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="rejection_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="product",
            name="reviewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="reviewed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="reviewed_vendor_products",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="submission_batch_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="unit_normalized",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.UniqueConstraint(
                fields=("vendor", "catalog_product", "brand_normalized", "quantity_normalized", "unit_normalized"),
                name="uniq_vendor_catalog_variant_signature",
            ),
        ),
    ]
