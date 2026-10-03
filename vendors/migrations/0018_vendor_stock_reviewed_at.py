from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('vendors', '0017_vendordocument_expires_on')]
    operations = [migrations.AddField(model_name='vendor', name='stock_reviewed_at', field=models.DateTimeField(null=True, blank=True))]
