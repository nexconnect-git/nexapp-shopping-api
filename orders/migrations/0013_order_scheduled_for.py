from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0012_order_wallet_discount'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='scheduled_for',
            field=models.DateTimeField(blank=True, help_text='Customer-requested delivery time', null=True),
        ),
    ]
