from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vendors', '0003_vendorpayout_deliverypartnerpayout'),
    ]

    operations = [
        migrations.AddField(
            model_name='vendor',
            name='require_stock_check',
            field=models.BooleanField(default=False),
        ),
    ]
