from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0024_customercontentblock'),
    ]

    operations = [
        migrations.AddField(
            model_name='platformsetting',
            name='cod_payment_qr',
            field=models.TextField(blank=True, default='', help_text='Optional manually uploaded data URL for pay-at-delivery QR.'),
        ),
    ]
