import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0033_order_fulfillment_traceability"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerRecommendationSnapshot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("recommended_product_ids", models.JSONField(blank=True, default=list)),
                ("flash_deal_product_ids", models.JSONField(blank=True, default=list)),
                ("recommended_store_ids", models.JSONField(blank=True, default=list)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("generated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="customer_recommendation_snapshot",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["user", "-generated_at"], name="cust_rec_user_generated_idx"),
                ],
            },
        ),
    ]
