import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0004_orderrating'),
        ('vendors', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Coupon',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('code', models.CharField(max_length=50, unique=True)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('discount_type', models.CharField(
                    choices=[('percentage', 'Percentage'), ('fixed', 'Fixed Amount'), ('free_delivery', 'Free Delivery')],
                    default='percentage', max_length=20,
                )),
                ('discount_value', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('min_order_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('max_discount_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('usage_limit', models.PositiveIntegerField(blank=True, null=True)),
                ('per_user_limit', models.PositiveIntegerField(default=1)),
                ('used_count', models.PositiveIntegerField(default=0)),
                ('valid_from', models.DateTimeField()),
                ('valid_until', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_coupons', to=settings.AUTH_USER_MODEL,
                )),
                ('vendor', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='coupons', to='vendors.vendor',
                )),
            ],
        ),
        migrations.AddField(
            model_name='order',
            name='coupon',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='orders', to='orders.coupon',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='coupon_discount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.CreateModel(
            name='CouponUsage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('discount_applied', models.DecimalField(decimal_places=2, max_digits=10)),
                ('used_at', models.DateTimeField(auto_now_add=True)),
                ('coupon', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='usages', to='orders.coupon',
                )),
                ('order', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='coupon_usages', to='orders.order',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='coupon_usages', to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
    ]
