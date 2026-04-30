import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_mobileotp'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminAuditLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('action', models.CharField(choices=[('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'), ('status_change', 'Status Change'), ('payout', 'Payout'), ('settings', 'Settings'), ('notification', 'Notification'), ('login', 'Login'), ('other', 'Other')], default='other', max_length=32)),
                ('entity_type', models.CharField(max_length=100)),
                ('entity_id', models.CharField(blank=True, max_length=100)),
                ('summary', models.CharField(max_length=255)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='admin_audit_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='adminauditlog',
            index=models.Index(fields=['action', 'created_at'], name='accounts_ad_action_cf4561_idx'),
        ),
        migrations.AddIndex(
            model_name='adminauditlog',
            index=models.Index(fields=['entity_type', 'entity_id'], name='accounts_ad_entity__3a69da_idx'),
        ),
    ]
