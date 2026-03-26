from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_user_force_password_change'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='temp_password',
            field=models.CharField(max_length=128, blank=True, default=''),
        ),
    ]
