import uuid
from django.db import models
from accounts.models import User, Address
from products.models import Product
from vendors.models import Vendor


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    STATUS_CHOICES = (
        ('placed', 'Placed'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready for Pickup'),
        ('picked_up', 'Picked Up'),
        ('on_the_way', 'On the Way'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='orders')
    delivery_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True)
    delivery_partner = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deliveries'
    )
    vendor_payout = models.ForeignKey(
        'vendors.VendorPayout', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders'
    )
    delivery_payout = models.ForeignKey(
        'vendors.DeliveryPartnerPayout', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='placed')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    PAYMENT_METHOD_CHOICES = (
        ('cod', 'Cash on Delivery'),
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cod')
    coupon = models.ForeignKey(
        'orders.Coupon', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders'
    )
    coupon_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    pickup_otp = models.CharField(max_length=6, blank=True, default='')
    delivery_otp = models.CharField(max_length=6, blank=True, default='')
    delivery_photo = models.ImageField(upload_to='delivery_photos/', null=True, blank=True)
    transaction_photo = models.ImageField(upload_to='transaction_photos/', null=True, blank=True)
    estimated_delivery_time = models.IntegerField(help_text='Estimated minutes', null=True, blank=True)
    actual_delivery_time = models.DateTimeField(null=True, blank=True)
    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    placed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orders'
        ordering = ['-placed_at']

    def __str__(self):
        return f"Order #{self.order_number}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=200)
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        app_label = 'orders'

    def __str__(self):
        return f"{self.quantity}x {self.product_name}"
