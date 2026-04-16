from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0011_order_refund_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='wallet_discount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
