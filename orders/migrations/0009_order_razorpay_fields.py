from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0008_platformsetting_order_transaction_photo'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='razorpay_order_id',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='order',
            name='razorpay_payment_id',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='order',
            name='is_payment_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='order',
            name='payment_method',
            field=models.CharField(
                choices=[('cod', 'Cash on Delivery'), ('razorpay', 'Razorpay (Online)')],
                default='cod',
                max_length=20,
            ),
        ),
    ]
