from django.db import models

class PlatformSetting(models.Model):
    upi_id = models.CharField(max_length=100, default='nexconnect@ybl')

    class Meta:
        app_label = 'orders'

    @classmethod
    def get_setting(cls):
        setting, _ = cls.objects.get_or_create(id=1)
        return setting
