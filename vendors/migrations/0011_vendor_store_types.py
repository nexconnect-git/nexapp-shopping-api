from django.db import migrations, models


STORE_TYPE_CHOICES = [
    ('wholesale_store', 'Wholesale Store'),
    ('retail_store', 'Retail Store'),
    ('kirana_store', 'Kirana Store'),
    ('supermarket', 'Supermarket'),
    ('hypermarket', 'Hypermarket'),
    ('department_store', 'Department Store'),
    ('specialty_store', 'Specialty Store'),
    ('convenience_store', 'Convenience Store'),
    ('discount_store', 'Discount Store'),
    ('franchise_store', 'Franchise Store'),
    ('chain_store', 'Chain Store'),
    ('online_store', 'Online Store / E-commerce'),
    ('street_vendor', 'Street Vendor / Hawker'),
    ('mandi_market_yard', 'Mandi / Market Yard'),
    ('b2b_store', 'B2B Store'),
]


def migrate_legacy_vendor_types(apps, schema_editor):
    Vendor = apps.get_model('vendors', 'Vendor')
    VendorOnboarding = apps.get_model('vendors', 'VendorOnboarding')
    legacy_values = ['individual', 'company', 'partnership', '']
    Vendor.objects.filter(vendor_type__in=legacy_values).update(
        vendor_type='retail_store',
    )
    VendorOnboarding.objects.filter(vendor_type__in=legacy_values).update(
        vendor_type='retail_store',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('vendors', '0010_alter_vendor_latitude_alter_vendor_longitude'),
    ]

    operations = [
        migrations.RunPython(
            migrate_legacy_vendor_types,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='vendor',
            name='vendor_type',
            field=models.CharField(
                blank=True,
                choices=STORE_TYPE_CHOICES,
                default='retail_store',
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name='vendoronboarding',
            name='vendor_type',
            field=models.CharField(
                choices=STORE_TYPE_CHOICES,
                default='retail_store',
                max_length=32,
            ),
        ),
    ]
