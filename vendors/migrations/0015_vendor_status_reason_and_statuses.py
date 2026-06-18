from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0014_vendor_document_license_path"),
    ]

    operations = [
        migrations.AddField(
            model_name="vendor",
            name="status_reason",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="vendor",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending Approval"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("hold", "Hold"),
                    ("suspended", "Suspended"),
                    ("in_review", "In Review"),
                    ("pending_details", "Pending Details"),
                    ("pending_documents", "Pending Documents"),
                    ("invalid_details", "Invalid Details"),
                    ("invalid_documents", "Invalid Documents"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
