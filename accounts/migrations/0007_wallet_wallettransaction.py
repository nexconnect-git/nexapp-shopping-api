import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_emailverification'),
    ]

    operations = [
        migrations.CreateModel(
            name='Wallet',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('balance', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='wallet', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'app_label': 'accounts',
            },
        ),
        migrations.CreateModel(
            name='WalletTransaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('transaction_type', models.CharField(choices=[('credit', 'Credit'), ('debit', 'Debit')], max_length=10)),
                ('source', models.CharField(choices=[('topup', 'Top-up'), ('refund', 'Refund'), ('order_payment', 'Order Payment'), ('admin', 'Admin Adjustment')], max_length=20)),
                ('reference_id', models.CharField(blank=True, default='', max_length=100)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('wallet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='accounts.wallet')),
            ],
            options={
                'app_label': 'accounts',
                'ordering': ['-created_at'],
            },
        ),
    ]
