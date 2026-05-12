from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0009_product_reapproval_audit_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='icon_name',
            field=models.CharField(
                blank=True,
                help_text='Material icon name used by customer apps when no category image is configured.',
                max_length=80,
            ),
        ),
    ]
