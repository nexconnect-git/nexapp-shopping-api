from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0005_coupon_couponusage_order_coupon'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderIssue',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('issue_type', models.CharField(choices=[
                    ('return', 'Return Request'),
                    ('refund', 'Refund Request'),
                    ('damage', 'Damaged Item'),
                    ('mismatch', 'Item Mismatch'),
                ], max_length=20)),
                ('description', models.TextField()),
                ('status', models.CharField(choices=[
                    ('open', 'Open'),
                    ('in_review', 'In Review'),
                    ('resolved', 'Resolved'),
                    ('rejected', 'Rejected'),
                    ('refund_initiated', 'Refund Initiated'),
                ], default='open', max_length=20)),
                ('admin_notes', models.TextField(blank=True)),
                ('refund_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('refund_method', models.CharField(blank=True, max_length=100)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='issues', to='orders.order')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='order_issues', to=settings.AUTH_USER_MODEL)),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_issues', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='IssueMessage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_admin', models.BooleanField(default=False)),
                ('message', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('issue', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='orders.orderissue')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='issue_messages', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
    ]
