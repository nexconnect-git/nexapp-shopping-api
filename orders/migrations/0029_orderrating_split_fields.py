from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0028_coupon_coupon_code_active_valid_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='orderrating',
            name='rating',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='orderrating',
            name='vendor_rating',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='orderrating',
            name='vendor_comment',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='orderrating',
            name='delivery_rating',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='orderrating',
            name='delivery_comment',
            field=models.TextField(blank=True, default=''),
        ),
    ]
