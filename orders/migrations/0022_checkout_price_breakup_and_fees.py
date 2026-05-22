from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0021_platformsetting_enabled_payment_methods'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='loyalty_discount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='order',
            name='packaging_fee',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='order',
            name='payment_metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='order',
            name='platform_fee',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='order',
            name='price_breakup',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='order',
            name='product_discount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='order',
            name='small_cart_fee',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='order',
            name='surge_fee',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='order',
            name='tax_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='platformsetting',
            name='packaging_fee',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Flat packaging fee displayed and charged at checkout.', max_digits=10),
        ),
        migrations.AddField(
            model_name='platformsetting',
            name='platform_fee',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Flat platform fee displayed and charged at checkout.', max_digits=10),
        ),
        migrations.AddField(
            model_name='platformsetting',
            name='small_cart_fee',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Fee applied when subtotal is below the small cart threshold.', max_digits=10),
        ),
        migrations.AddField(
            model_name='platformsetting',
            name='small_cart_threshold',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Apply small cart fee below this subtotal. Set 0 to disable.', max_digits=10),
        ),
        migrations.AddField(
            model_name='platformsetting',
            name='surge_fee',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Temporary checkout surge fee. Set 0 to disable.', max_digits=10),
        ),
        migrations.AddField(
            model_name='platformsetting',
            name='tax_percentage',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Checkout tax/GST percentage applied to taxable display total.', max_digits=5),
        ),
    ]
