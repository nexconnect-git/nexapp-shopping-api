from django.db import migrations, models


def set_default_currency(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    User.objects.filter(currency__isnull=True).update(currency='INR')
    User.objects.filter(currency='').update(currency='INR')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0017_mobileotp_attempts'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='country',
            field=models.CharField(blank=True, default='IN', max_length=2),
        ),
        migrations.AddField(
            model_name='user',
            name='currency',
            field=models.CharField(
                choices=[
                    ('INR', 'Indian Rupee'),
                    ('USD', 'US Dollar'),
                    ('EUR', 'Euro'),
                    ('GBP', 'British Pound'),
                    ('AUD', 'Australian Dollar'),
                    ('CAD', 'Canadian Dollar'),
                    ('SGD', 'Singapore Dollar'),
                    ('AED', 'UAE Dirham'),
                    ('SAR', 'Saudi Riyal'),
                    ('QAR', 'Qatari Riyal'),
                    ('KWD', 'Kuwaiti Dinar'),
                    ('BHD', 'Bahraini Dinar'),
                    ('OMR', 'Omani Rial'),
                    ('JPY', 'Japanese Yen'),
                    ('CNY', 'Chinese Yuan'),
                    ('HKD', 'Hong Kong Dollar'),
                    ('CHF', 'Swiss Franc'),
                    ('SEK', 'Swedish Krona'),
                    ('NOK', 'Norwegian Krone'),
                    ('DKK', 'Danish Krone'),
                    ('NZD', 'New Zealand Dollar'),
                    ('ZAR', 'South African Rand'),
                    ('BRL', 'Brazilian Real'),
                    ('MXN', 'Mexican Peso'),
                    ('KRW', 'South Korean Won'),
                    ('THB', 'Thai Baht'),
                    ('MYR', 'Malaysian Ringgit'),
                    ('IDR', 'Indonesian Rupiah'),
                    ('PHP', 'Philippine Peso'),
                    ('PKR', 'Pakistani Rupee'),
                    ('BDT', 'Bangladeshi Taka'),
                    ('LKR', 'Sri Lankan Rupee'),
                    ('NGN', 'Nigerian Naira'),
                    ('EGP', 'Egyptian Pound'),
                    ('TRY', 'Turkish Lira'),
                    ('RUB', 'Russian Ruble'),
                    ('PLN', 'Polish Zloty'),
                    ('CZK', 'Czech Koruna'),
                    ('HUF', 'Hungarian Forint'),
                    ('ILS', 'Israeli New Shekel'),
                ],
                default='INR',
                max_length=3,
            ),
        ),
        migrations.RunPython(set_default_currency, migrations.RunPython.noop),
    ]
