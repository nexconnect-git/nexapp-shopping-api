from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0015_alter_address_latitude_alter_address_longitude'),
    ]

    operations = [
        migrations.AddField(
            model_name='mobileotp',
            name='email',
            field=models.EmailField(blank=True, default='', max_length=254),
        ),
    ]
