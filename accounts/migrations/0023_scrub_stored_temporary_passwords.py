from django.db import migrations


def scrub_temporary_passwords(apps, schema_editor):
    # Preserve actual password hashes while removing legacy plaintext copies.
    apps.get_model('accounts', 'User').objects.exclude(temp_password='').update(temp_password='')


class Migration(migrations.Migration):
    dependencies = [('accounts', '0022_alter_adminpermissiongrant_permission')]
    operations = [migrations.RunPython(scrub_temporary_passwords, migrations.RunPython.noop)]
