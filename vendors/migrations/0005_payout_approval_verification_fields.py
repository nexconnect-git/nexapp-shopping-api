from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vendors', '0004_vendor_require_stock_check'),
    ]

    operations = [
        # ── VendorPayout ────────────────────────────────────────────────────────
        migrations.AlterField(
            model_name='vendorpayout',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending_approval', 'Pending Vendor Approval'),
                    ('approved',         'Approved by Vendor'),
                    ('scheduled',        'Scheduled for Processing'),
                    ('pending_verify',   'Pending Credit Verification'),
                    ('verified',         'Verified by Vendor'),
                    ('paid',             'Paid (Admin Override)'),
                    ('failed',           'Failed'),
                ],
                default='pending_approval',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='vendorpayout',
            name='vendor_approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vendorpayout',
            name='payment_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vendorpayout',
            name='vendor_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vendorpayout',
            name='vendor_rejection_reason',
            field=models.CharField(blank=True, max_length=500),
        ),
        # ── DeliveryPartnerPayout ───────────────────────────────────────────────
        migrations.AlterField(
            model_name='deliverypartnerpayout',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending_approval', 'Pending Vendor Approval'),
                    ('approved',         'Approved by Vendor'),
                    ('scheduled',        'Scheduled for Processing'),
                    ('pending_verify',   'Pending Credit Verification'),
                    ('verified',         'Verified by Vendor'),
                    ('paid',             'Paid (Admin Override)'),
                    ('failed',           'Failed'),
                ],
                default='pending_approval',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='deliverypartnerpayout',
            name='partner_approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='deliverypartnerpayout',
            name='payment_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='deliverypartnerpayout',
            name='partner_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='deliverypartnerpayout',
            name='partner_rejection_reason',
            field=models.CharField(blank=True, max_length=500),
        ),
        # Migrate existing 'pending' rows to 'pending_approval'
        migrations.RunSQL(
            sql="UPDATE vendors_vendorpayout SET status='pending_approval' WHERE status='pending';",
            reverse_sql="UPDATE vendors_vendorpayout SET status='pending' WHERE status='pending_approval';",
        ),
        migrations.RunSQL(
            sql="UPDATE vendors_deliverypartnerpayout SET status='pending_approval' WHERE status='pending';",
            reverse_sql="UPDATE vendors_deliverypartnerpayout SET status='pending' WHERE status='pending_approval';",
        ),
    ]
