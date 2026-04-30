from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0008_vendor_inheritance_workflow_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="approval_change_summary",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="product",
            name="approval_requested_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
