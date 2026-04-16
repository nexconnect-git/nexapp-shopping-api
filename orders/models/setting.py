from decimal import Decimal
from django.db import models


class PlatformSetting(models.Model):
    upi_id = models.CharField(max_length=100, default='nexconnect@ybl')

    # Delivery fee rate card
    delivery_base_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('30.00'),
        help_text='Base delivery fee in ₹ regardless of distance.'
    )
    delivery_per_km_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('5.00'),
        help_text='Additional ₹ charged per km of distance.'
    )
    free_delivery_above = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Orders with subtotal above this amount get free delivery. Set 0 to disable.'
    )

    # Cancellation policy
    cancellation_window_minutes = models.IntegerField(
        default=10,
        help_text='Minutes after placement within which customer can cancel. 0 = always allowed.'
    )
    cancellation_allowed_statuses = models.JSONField(
        default=list,
        help_text="Statuses from which cancellation is allowed, e.g. [\"placed\",\"confirmed\"]."
    )

    class Meta:
        app_label = 'orders'

    @classmethod
    def get_setting(cls):
        setting, _ = cls.objects.get_or_create(id=1)
        return setting
