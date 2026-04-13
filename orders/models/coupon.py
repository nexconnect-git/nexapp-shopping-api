import uuid
from decimal import Decimal
from django.db import models
from accounts.models import User


class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
        ('free_delivery', 'Free Delivery'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='percentage')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # If vendor is set, this coupon is vendor-specific; None = platform-wide (admin)
    vendor = models.ForeignKey(
        'vendors.Vendor', on_delete=models.CASCADE, null=True, blank=True, related_name='coupons'
    )
    is_active = models.BooleanField(default=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text='Blank = unlimited')
    per_user_limit = models.PositiveIntegerField(default=1, help_text='Max uses per customer')
    used_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_coupons')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'orders'

    def __str__(self):
        return f"{self.code} — {self.title}"

    def calculate_discount(self, order_total):
        """Return the discount amount for a given order total."""
        total = Decimal(str(order_total))
        if self.discount_type == 'free_delivery':
            return Decimal('0')  # handled separately
        if self.discount_type == 'percentage':
            discount = total * (self.discount_value / 100)
        else:  # fixed
            discount = self.discount_value
        if self.max_discount_amount:
            discount = min(discount, self.max_discount_amount)
        return min(discount, total)


class CouponUsage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coupon_usages')
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='coupon_usages')
    discount_applied = models.DecimalField(max_digits=10, decimal_places=2)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'orders'

    def __str__(self):
        return f"{self.coupon.code} used by {self.user.username}"
