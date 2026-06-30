"""Serializers for cart-related models."""

from rest_framework import serializers

from orders.models import Cart, CartItem
from products.data.product_repository import ProductRepository
from products.models import Product
from products.serializers import ProductListSerializer


class CartItemSerializer(serializers.ModelSerializer):
    """Serializer for a single cart item with nested product and subtotal."""

    product = ProductListSerializer(read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ["id", "product", "quantity", "price_at_add", "subtotal", "added_at"]
        read_only_fields = ["id", "added_at"]


class CartSerializer(serializers.ModelSerializer):
    """Serializer for a customer's cart with nested items and totals."""

    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    fulfillment_node_id = serializers.UUIDField(read_only=True)
    fulfillment_node_name = serializers.CharField(source="fulfillment_node.name", read_only=True)

    class Meta:
        model = Cart
        fields = [
            "id",
            "items",
            "total_items",
            "total_amount",
            "fulfillment_node_id",
            "fulfillment_node_name",
            "fulfillment_promise_id",
            "fulfillment_promise_expires_at",
            "fulfillment_locked_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AddToCartSerializer(serializers.Serializer):
    """Write serializer for adding a product to the cart."""

    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    fulfillment_node_id = serializers.UUIDField(required=False, allow_null=True)
    fulfillment_promise_id = serializers.CharField(required=False, allow_blank=True, default="")
    fulfillment_promise_expires_at = serializers.DateTimeField(required=False, allow_null=True)

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
            product = Product.objects.get(
                id=value,
                **ProductRepository.customer_visible_filter(),
            )
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or unavailable.")
        if product.stock < 1:
            raise serializers.ValidationError("Product is out of stock.")
        return value


class ReplaceCartSerializer(AddToCartSerializer):
    """Write serializer for atomically replacing the cart with one product."""


class RefreshCartFulfillmentSerializer(serializers.Serializer):
    """Write serializer for refreshing a cart's active fulfillment promise."""

    fulfillment_node_id = serializers.UUIDField()
    fulfillment_promise_id = serializers.CharField(required=False, allow_blank=True, default="")
    fulfillment_promise_expires_at = serializers.DateTimeField(required=False, allow_null=True)


class CartFulfillmentEventSerializer(serializers.Serializer):
    """Serializer for customer cart fulfillment audit events."""

    EVENT_CHOICES = (
        ("cart_fulfillment_conflict", "Cart fulfillment conflict"),
        ("cart_fulfillment_invalidated", "Cart fulfillment invalidated"),
        ("cart_fulfillment_kept", "Cart fulfillment kept"),
        ("cart_fulfillment_rehydrated", "Cart fulfillment rehydrated"),
        ("cart_fulfillment_refresh_failed", "Cart fulfillment refresh failed"),
    )

    event_type = serializers.ChoiceField(choices=EVENT_CHOICES)
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_metadata(self, value):
        return value if isinstance(value, dict) else {}
