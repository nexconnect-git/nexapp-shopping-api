import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
        ('delivery', 'Delivery Partner'),
        ('admin', 'Admin'),
    )
    CURRENCY_CHOICES = (
        ('INR', 'Indian Rupee'),
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
        ('AUD', 'Australian Dollar'),
        ('CAD', 'Canadian Dollar'),
        ('SGD', 'Singapore Dollar'),
        ('AED', 'UAE Dirham'),
        ('SAR', 'Saudi Riyal'),
        ('QAR', 'Qatari Riyal'),
        ('KWD', 'Kuwaiti Dinar'),
        ('BHD', 'Bahraini Dinar'),
        ('OMR', 'Omani Rial'),
        ('JPY', 'Japanese Yen'),
        ('CNY', 'Chinese Yuan'),
        ('HKD', 'Hong Kong Dollar'),
        ('CHF', 'Swiss Franc'),
        ('SEK', 'Swedish Krona'),
        ('NOK', 'Norwegian Krone'),
        ('DKK', 'Danish Krone'),
        ('NZD', 'New Zealand Dollar'),
        ('ZAR', 'South African Rand'),
        ('BRL', 'Brazilian Real'),
        ('MXN', 'Mexican Peso'),
        ('KRW', 'South Korean Won'),
        ('THB', 'Thai Baht'),
        ('MYR', 'Malaysian Ringgit'),
        ('IDR', 'Indonesian Rupiah'),
        ('PHP', 'Philippine Peso'),
        ('PKR', 'Pakistani Rupee'),
        ('BDT', 'Bangladeshi Taka'),
        ('LKR', 'Sri Lankan Rupee'),
        ('NGN', 'Nigerian Naira'),
        ('EGP', 'Egyptian Pound'),
        ('TRY', 'Turkish Lira'),
        ('RUB', 'Russian Ruble'),
        ('PLN', 'Polish Zloty'),
        ('CZK', 'Czech Koruna'),
        ('HUF', 'Hungarian Forint'),
        ('ILS', 'Israeli New Shekel'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    phone = models.CharField(max_length=15, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    force_password_change = models.BooleanField(default=False)
    temp_password = models.CharField(max_length=128, blank=True, default='')
    country = models.CharField(max_length=2, blank=True, default='IN')
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='INR')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'accounts'

    def __str__(self):
        return f"{self.username} ({self.role})"
