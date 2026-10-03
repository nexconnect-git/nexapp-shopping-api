from django.db import migrations

def invalidate_legacy_tokens(apps, schema_editor):
    # Existing plaintext reset links are revoked; new tokens store only a digest.
    apps.get_model('accounts', 'PasswordResetToken').objects.filter(used=False).update(used=True)

class Migration(migrations.Migration):
    dependencies = [('accounts', '0020_wallettopup')]
    operations = [migrations.RunPython(invalidate_legacy_tokens, migrations.RunPython.noop)]
