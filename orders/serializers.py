from rest_framework import serializers
from .models import Cart, CartItem, Order, OrderItem, OrderTracking
from accounts.serializers import AddressSerializer
from products.serializers import ProductListSerializer


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'quantity', 'subtotal', 'added_at']
        read_only_fields = ['id', 'added_at']


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total_items', 'total_amount', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AddToCartSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate_product_id(self, value):
        from products.models import Product
        try:
            product = Product.objects.get(id=value, is_available=True)
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or unavailable.")
        if product.stock < 1:
            raise serializers.ValidationError("Product is out of stock.")
        return value


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'product_price', 'quantity', 'subtotal']
        read_only_fields = ['id']


class OrderTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderTracking
        fields = ['id', 'status', 'description', 'latitude', 'longitude', 'timestamp']
        read_only_fields = ['id', 'timestamp']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    tracking = OrderTrackingSerializer(many=True, read_only=True)
    delivery_address = AddressSerializer(read_only=True)
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    vendor_name = serializers.CharField(source='vendor.store_name', read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'order_number', 'customer', 'customer_name', 'vendor',
                  'vendor_name', 'delivery_address', 'delivery_partner', 'status',
                  'payment_method', 'subtotal', 'delivery_fee', 'discount', 'total',
                  'notes', 'delivery_otp', 'delivery_photo',
                  'estimated_delivery_time', 'actual_delivery_time',
                  'delivery_latitude', 'delivery_longitude',
                  'placed_at', 'updated_at', 'items', 'tracking']
        read_only_fields = ['id', 'order_number', 'customer', 'placed_at', 'updated_at']


class CreateOrderSerializer(serializers.Serializer):
    delivery_address_id = serializers.UUIDField()
    payment_method = serializers.ChoiceField(choices=['cod'], default='cod')
    notes = serializers.CharField(required=False, default='', allow_blank=True)

    def validate_delivery_address_id(self, value):
        from accounts.models import Address
        user = self.context['request'].user
        try:
            Address.objects.get(id=value, user=user)
        except Address.DoesNotExist:
            raise serializers.ValidationError("Address not found.")
        return value
