import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('vendors', '0007_vendor_wallet_balance'),
    ]

    operations = [
        migrations.CreateModel(
            name='VendorWalletTransaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('transaction_type', models.CharField(choices=[('credit', 'Credit'), ('debit', 'Debit')], max_length=10)),
                ('source', models.CharField(choices=[('order_earning', 'Order Earning'), ('payout_withdrawal', 'Payout Withdrawal'), ('admin_adjustment', 'Admin Adjustment'), ('refund_deduction', 'Refund Deduction')], max_length=20)),
                ('reference_id', models.CharField(blank=True, default='', max_length=100)),
                ('description', models.TextField(blank=True)),
                ('balance_after', models.DecimalField(decimal_places=2, default=0, help_text='Running balance after this transaction', max_digits=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('vendor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wallet_transactions', to='vendors.vendor')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
