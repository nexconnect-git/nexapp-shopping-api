from django.db import migrations, models


def seed_enabled_payment_methods(apps, schema_editor):
    PlatformSetting = apps.get_model('orders', 'PlatformSetting')
    default_methods = [
        'razorpay_upi',
        'razorpay_card',
        'razorpay_wallet',
        'razorpay_netbanking',
        'cod',
    ]
    for setting in PlatformSetting.objects.all():
        if not setting.enabled_payment_methods:
            setting.enabled_payment_methods = default_methods
            setting.save(update_fields=['enabled_payment_methods'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0020_coupon_presentation_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='platformsetting',
            name='enabled_payment_methods',
            field=models.JSONField(blank=True, default=list, help_text='Enabled customer checkout payment method keys.'),
        ),
        migrations.RunPython(seed_enabled_payment_methods, migrations.RunPython.noop),
    ]
