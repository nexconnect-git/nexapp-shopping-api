from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0023_alter_order_delivery_photo_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomerContentBlock',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('placement', models.CharField(choices=[('home_ad', 'Home promo card'), ('home_engagement', 'Home engagement banner'), ('offers_shop', 'Offers page banner'), ('search_ad', 'Search page banner'), ('store_listing_ad', 'Store listing banner'), ('store_detail_ad', 'Store detail banner')], max_length=32)),
                ('template', models.CharField(choices=[('soft_card', 'Soft promo card'), ('club_banner', 'Club banner'), ('image_card', 'Image card')], default='soft_card', max_length=32)),
                ('eyebrow', models.CharField(blank=True, max_length=40)),
                ('title', models.CharField(max_length=100)),
                ('subtitle', models.CharField(blank=True, max_length=220)),
                ('cta_label', models.CharField(default='Shop now', max_length=40)),
                ('cta_url', models.CharField(default='/stores', max_length=255)),
                ('icon', models.CharField(blank=True, max_length=48)),
                ('tone', models.CharField(choices=[('purple', 'Purple'), ('green', 'Green'), ('orange', 'Orange'), ('red', 'Red'), ('blue', 'Blue')], default='purple', max_length=16)),
                ('image', models.URLField(blank=True, max_length=500)),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('starts_at', models.DateTimeField(blank=True, null=True)),
                ('ends_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['placement', 'display_order', 'created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='customercontentblock',
            index=models.Index(fields=['placement', 'is_active', 'display_order'], name='orders_cust_placeme_deb347_idx'),
        ),
        migrations.AddIndex(
            model_name='customercontentblock',
            index=models.Index(fields=['starts_at', 'ends_at'], name='orders_cust_starts__3b619b_idx'),
        ),
    ]
