from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0016_mobileotp_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='mobileotp',
            name='attempts',
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
