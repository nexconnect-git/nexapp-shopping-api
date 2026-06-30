import uuid
from django.db import models
from django.db.models import Q
from accounts.models import User, Address
from products.models import CatalogProduct
from helpers.upload_paths import UserDateUploadPath
from products.models import Product
from vendors.models import FulfillmentNode, Vendor


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
    fulfillment_node = models.ForeignKey(
        FulfillmentNode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
    )
    fulfillment_promise_id = models.CharField(max_length=160, blank=True, default='')
    fulfillment_promise_expires_at = models.DateTimeField(null=True, blank=True)
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
    product_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    packaging_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    small_cart_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    surge_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    PAYMENT_METHOD_CHOICES = (
        ('cod', 'Cash on Delivery'),
        ('razorpay', 'Razorpay (Online)'),
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cod')
    razorpay_order_id = models.CharField(max_length=100, blank=True, default='')
    razorpay_payment_id = models.CharField(max_length=100, blank=True, default='')
    razorpay_refund_id = models.CharField(max_length=100, blank=True, default='')
    REFUND_STATUS_CHOICES = (
        ('none', 'No Refund'),
        ('initiated', 'Refund Initiated'),
        ('processed', 'Refund Processed'),
        ('failed', 'Refund Failed'),
    )
    refund_status = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default='none')
    is_payment_verified = models.BooleanField(default=False)
    coupon = models.ForeignKey(
        'orders.Coupon', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders'
    )
    coupon_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    wallet_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    loyalty_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_breakup = models.JSONField(default=dict, blank=True)
    payment_metadata = models.JSONField(default=dict, blank=True)
    client_idempotency_key = models.CharField(max_length=120, blank=True, default='', db_index=True)
    scheduled_for = models.DateTimeField(null=True, blank=True, help_text='Customer-requested delivery time')
    notes = models.TextField(blank=True)
    pickup_otp = models.CharField(max_length=6, blank=True, default='')
    delivery_otp = models.CharField(max_length=6, blank=True, default='')
    delivery_photo = models.ImageField(upload_to=UserDateUploadPath('delivery_proof'), null=True, blank=True)
    transaction_photo = models.ImageField(upload_to=UserDateUploadPath('transaction_proof'), null=True, blank=True)
    estimated_delivery_time = models.IntegerField(help_text='Estimated minutes', null=True, blank=True)
    actual_delivery_time = models.DateTimeField(null=True, blank=True)
    delivery_latitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    delivery_longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    delivery_tip = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    placed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orders'
        ordering = ['-placed_at']
        indexes = [
            models.Index(fields=['customer', 'status', '-placed_at'], name='ord_cust_status_placed_idx'),
            models.Index(fields=['vendor', 'status', '-placed_at'], name='ord_vendor_status_pl_idx'),
            models.Index(fields=['delivery_partner', 'status'], name='ord_delivery_status_idx'),
            models.Index(fields=['status', '-placed_at'], name='ord_status_placed_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['customer', 'vendor', 'client_idempotency_key'],
                condition=~Q(client_idempotency_key=''),
                name='unique_order_idempotency_per_customer_vendor',
            ),
        ]

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
    catalog_product = models.ForeignKey(
        CatalogProduct,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_item_snapshots',
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_item_snapshots',
    )
    fulfillment_node = models.ForeignKey(
        FulfillmentNode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_item_snapshots',
    )
    product_name = models.CharField(max_length=200)
    product_brand = models.CharField(max_length=120, blank=True)
    product_unit = models.CharField(max_length=20, blank=True)
    product_pack_size = models.CharField(max_length=50, blank=True)
    product_sku = models.CharField(max_length=50, blank=True)
    product_slug = models.SlugField(blank=True)
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    product_compare_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        app_label = 'orders'

    def __str__(self):
        return f"{self.quantity}x {self.product_name}"
