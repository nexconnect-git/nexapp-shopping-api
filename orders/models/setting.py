from decimal import Decimal
from django.db import models


class PlatformSetting(models.Model):
    PAYMENT_METHOD_COD = 'cod'
    PAYMENT_METHOD_UPI = 'razorpay_upi'
    PAYMENT_METHOD_CARD = 'razorpay_card'
    PAYMENT_METHOD_WALLET = 'razorpay_wallet'
    PAYMENT_METHOD_NETBANKING = 'razorpay_netbanking'
    DEFAULT_PAYMENT_METHODS = [
        PAYMENT_METHOD_UPI,
        PAYMENT_METHOD_CARD,
        PAYMENT_METHOD_WALLET,
        PAYMENT_METHOD_NETBANKING,
        PAYMENT_METHOD_COD,
    ]

    upi_id = models.CharField(max_length=100, default='nexconnect@ybl')
    enabled_payment_methods = models.JSONField(
        default=list,
        blank=True,
        help_text='Enabled customer checkout payment method keys.'
    )

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
    platform_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Flat platform fee displayed and charged at checkout.'
    )
    packaging_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Flat packaging fee displayed and charged at checkout.'
    )
    small_cart_threshold = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Apply small cart fee below this subtotal. Set 0 to disable.'
    )
    small_cart_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Fee applied when subtotal is below the small cart threshold.'
    )
    tax_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Checkout tax/GST percentage applied to taxable display total.'
    )
    surge_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Temporary checkout surge fee. Set 0 to disable.'
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
        if not setting.enabled_payment_methods:
            setting.enabled_payment_methods = cls.DEFAULT_PAYMENT_METHODS.copy()
            setting.save(update_fields=['enabled_payment_methods'])
        return setting

    def normalized_payment_methods(self):
        valid = set(self.DEFAULT_PAYMENT_METHODS)
        methods = self.enabled_payment_methods or self.DEFAULT_PAYMENT_METHODS
        return [method for method in methods if method in valid]

    def is_cod_enabled(self):
        return self.PAYMENT_METHOD_COD in self.normalized_payment_methods()

    def is_online_payment_enabled(self):
        return any(method.startswith('razorpay_') for method in self.normalized_payment_methods())
