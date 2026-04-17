from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0014_platform_banner'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='delivery_tip',
            field=models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0')),
        ),
    ]
