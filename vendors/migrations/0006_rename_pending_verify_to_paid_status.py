from django.db import migrations, models


PAYOUT_STATUS_CHOICES = [
    ('pending_approval', 'Pending Vendor Approval'),
    ('approved',         'Approved by Vendor'),
    ('scheduled',        'Scheduled for Processing'),
    ('paid',             'Payment Dispatched — Awaiting Verification'),
    ('verified',         'Verified'),
    ('failed',           'Failed'),
]


def rename_pending_verify_to_paid(apps, _schema_editor):
    VendorPayout = apps.get_model('vendors', 'VendorPayout')
    DeliveryPartnerPayout = apps.get_model('vendors', 'DeliveryPartnerPayout')
    VendorPayout.objects.filter(status='pending_verify').update(status='paid')
    DeliveryPartnerPayout.objects.filter(status='pending_verify').update(status='paid')


def reverse_rename(apps, _schema_editor):
    VendorPayout = apps.get_model('vendors', 'VendorPayout')
    DeliveryPartnerPayout = apps.get_model('vendors', 'DeliveryPartnerPayout')
    VendorPayout.objects.filter(status='paid').update(status='pending_verify')
    DeliveryPartnerPayout.objects.filter(status='paid').update(status='pending_verify')


class Migration(migrations.Migration):

    dependencies = [
        ('vendors', '0005_payout_approval_verification_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vendorpayout',
            name='status',
            field=models.CharField(
                choices=PAYOUT_STATUS_CHOICES,
                default='pending_approval',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='deliverypartnerpayout',
            name='status',
            field=models.CharField(
                choices=PAYOUT_STATUS_CHOICES,
                default='pending_approval',
                max_length=20,
            ),
        ),
        migrations.RunPython(rename_pending_verify_to_paid, reverse_rename),
    ]
