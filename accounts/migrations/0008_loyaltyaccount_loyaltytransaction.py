import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_wallet_wallettransaction'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoyaltyAccount',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('points', models.IntegerField(default=0)),
                ('lifetime_points', models.IntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='loyalty', to=settings.AUTH_USER_MODEL)),
            ],
            options={'app_label': 'accounts'},
        ),
        migrations.CreateModel(
            name='LoyaltyTransaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('points', models.IntegerField()),
                ('transaction_type', models.CharField(choices=[('earn', 'Earned'), ('redeem', 'Redeemed'), ('expire', 'Expired'), ('adjust', 'Admin Adjustment')], max_length=10)),
                ('reference_id', models.CharField(blank=True, default='', max_length=100)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='accounts.loyaltyaccount')),
            ],
            options={'app_label': 'accounts', 'ordering': ['-created_at']},
        ),
    ]
