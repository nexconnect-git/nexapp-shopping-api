from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0013_order_scheduled_for'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformBanner',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=100)),
                ('subtitle', models.CharField(blank=True, max_length=200)),
                ('badge_text', models.CharField(blank=True, max_length=40)),
                ('cta_label', models.CharField(default='Order Now', max_length=40)),
                ('cta_url', models.CharField(default='/shops', max_length=255)),
                ('image', models.ImageField(blank=True, null=True, upload_to='banners/')),
                ('bg_gradient', models.CharField(
                    default='linear-gradient(135deg,#6c63ff,#5046e4)',
                    help_text='CSS gradient string used as background when no image is set.',
                    max_length=120,
                )),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['display_order', 'created_at'],
            },
        ),
    ]
