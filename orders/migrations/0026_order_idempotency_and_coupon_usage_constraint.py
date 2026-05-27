from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vendors', '0012_alter_vendor_banner_alter_vendor_logo_and_more'),
        ('orders', '0025_platformsetting_cod_payment_qr'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='client_idempotency_key',
            field=models.CharField(blank=True, db_index=True, default='', max_length=120),
        ),
        migrations.AddConstraint(
            model_name='order',
            constraint=models.UniqueConstraint(
                condition=~models.Q(client_idempotency_key=''),
                fields=('customer', 'vendor', 'client_idempotency_key'),
                name='unique_order_idempotency_per_customer_vendor',
            ),
        ),
        migrations.AddConstraint(
            model_name='couponusage',
            constraint=models.UniqueConstraint(
                fields=('coupon', 'user', 'order'),
                name='unique_coupon_usage_per_order',
            ),
        ),
    ]
