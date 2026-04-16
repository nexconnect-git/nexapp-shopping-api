from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_product_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='show_in_customer_ui',
            field=models.BooleanField(
                default=True,
                help_text='Controls visibility in the customer app. Vendor-created categories default to False until admin approves.',
            ),
        ),
    ]
