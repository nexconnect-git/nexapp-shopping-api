import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0026_order_idempotency_and_coupon_usage_constraint'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('gateway', models.CharField(default='razorpay', max_length=40)),
                ('gateway_order_id', models.CharField(max_length=120, unique=True)),
                ('gateway_payment_id', models.CharField(blank=True, db_index=True, default='', max_length=120)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('currency', models.CharField(default='INR', max_length=8)),
                ('status', models.CharField(choices=[('created', 'Created'), ('pending', 'Pending'), ('authorized', 'Authorized'), ('paid', 'Paid'), ('failed', 'Failed'), ('refunded', 'Refunded'), ('reconciled', 'Reconciled')], default='created', max_length=20)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('last_event_id', models.CharField(blank=True, default='', max_length=120)),
                ('mismatch_reason', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_sessions', to=settings.AUTH_USER_MODEL)),
                ('orders', models.ManyToManyField(blank=True, related_name='payment_sessions', to='orders.order')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['customer', 'status', 'created_at'], name='orders_paym_custome_236582_idx'),
                    models.Index(fields=['gateway_order_id', 'status'], name='orders_paym_gateway_d9553e_idx'),
                ],
            },
        ),
    ]
