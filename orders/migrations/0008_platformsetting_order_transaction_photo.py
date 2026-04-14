from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0007_order_delivery_payout_order_vendor_payout_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('upi_id', models.CharField(default='nexconnect@ybl', max_length=100)),
            ],
        ),
        migrations.AddField(
            model_name='order',
            name='transaction_photo',
            field=models.ImageField(blank=True, null=True, upload_to='transaction_photos/'),
        ),
    ]
