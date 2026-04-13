"""Serializers for cart-related models."""

from rest_framework import serializers

from orders.models import Cart, CartItem
from products.models import Product
from products.serializers import ProductListSerializer


class CartItemSerializer(serializers.ModelSerializer):
    """Serializer for a single cart item with nested product and subtotal."""

    product = ProductListSerializer(read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ["id", "product", "quantity", "subtotal", "added_at"]
        read_only_fields = ["id", "added_at"]


class CartSerializer(serializers.ModelSerializer):
    """Serializer for a customer's cart with nested items and totals."""

    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = ["id", "items", "total_items", "total_amount", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class AddToCartSerializer(serializers.Serializer):
    """Write serializer for adding a product to the cart."""

    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate_product_id(self, value):
        """Verify the product exists, is available, and has stock.

        Args:
            value: UUID of the product to add.

        Returns:
            The validated product UUID.

        Raises:
            ValidationError: If the product is not found, unavailable, or out of stock.
        """
        try:
            product = Product.objects.get(id=value, is_available=True)
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or unavailable.")
        if product.stock < 1:
            raise serializers.ValidationError("Product is out of stock.")
        return value
