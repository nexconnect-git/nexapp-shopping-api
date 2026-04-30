from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_add_address_landmark'),
    ]

    operations = [
        migrations.CreateModel(
            name='MobileOTP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone', models.CharField(db_index=True, max_length=20)),
                ('purpose', models.CharField(choices=[('login', 'Login'), ('register', 'Register')], max_length=20)),
                ('otp_hash', models.CharField(max_length=128)),
                ('is_used', models.BooleanField(default=False)),
                ('expires_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
