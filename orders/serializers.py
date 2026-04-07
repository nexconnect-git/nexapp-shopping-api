"""
Serializers for the ``orders`` app.

Covers cart, order, coupon, rating, order issues, and issue messaging.
"""

from rest_framework import serializers

from accounts.serializers import AddressSerializer
from orders.models import (
    Cart,
    CartItem,
    Coupon,
    IssueMessage,
    Order,
    OrderIssue,
    OrderItem,
    OrderRating,
    OrderTracking,
)
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


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for a single line item within an order."""

    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_name", "product_price", "quantity", "subtotal"]
        read_only_fields = ["id"]


class OrderTrackingSerializer(serializers.ModelSerializer):
    """Serializer for an order tracking event."""

    class Meta:
        model = OrderTracking
        fields = ["id", "status", "description", "latitude", "longitude", "timestamp"]
        read_only_fields = ["id", "timestamp"]


class OrderSerializer(serializers.ModelSerializer):
    """Full order serializer with nested items, tracking, address, and delivery info."""

    items = OrderItemSerializer(many=True, read_only=True)
    tracking = OrderTrackingSerializer(many=True, read_only=True)
    delivery_address = AddressSerializer(read_only=True)
    customer_name = serializers.CharField(source="customer.get_full_name", read_only=True)
    vendor_name = serializers.CharField(source="vendor.store_name", read_only=True)
    vendor_info = serializers.SerializerMethodField()
    delivery_partner_info = serializers.SerializerMethodField()
    assignment_status = serializers.SerializerMethodField()
    invoice_id = serializers.SerializerMethodField()
    has_rating = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id", "order_number", "customer", "customer_name", "vendor",
            "vendor_name", "vendor_info", "delivery_address", "delivery_partner",
            "delivery_partner_info", "status", "assignment_status", "invoice_id",
            "has_rating", "payment_method", "subtotal", "delivery_fee", "discount",
            "coupon_discount", "total",
            "notes", "pickup_otp", "delivery_otp", "delivery_photo",
            "estimated_delivery_time", "actual_delivery_time",
            "delivery_latitude", "delivery_longitude",
            "vendor_payout", "delivery_payout",
            "placed_at", "updated_at", "items", "tracking",
        ]
        read_only_fields = [
            "id", "order_number", "customer", "placed_at", "updated_at",
            "vendor_payout", "delivery_payout",
        ]

    def get_vendor_info(self, obj) -> dict:
        """Return key vendor fields embedded in the order response.

        Args:
            obj: The ``Order`` instance.

        Returns:
            Dictionary with vendor id, store name, address, and contact info.
        """
        vendor = obj.vendor
        return {
            "id": str(vendor.id),
            "store_name": vendor.store_name,
            "address": vendor.address,
            "latitude": str(vendor.latitude) if vendor.latitude else None,
            "longitude": str(vendor.longitude) if vendor.longitude else None,
            "phone": vendor.phone,
        }

    def get_delivery_partner_info(self, obj) -> dict | None:
        """Return delivery partner details, or ``None`` if not yet assigned.

        Args:
            obj: The ``Order`` instance.

        Returns:
            Dictionary with partner id, name, vehicle info, and rating, or ``None``.
        """
        if not obj.delivery_partner:
            return None
        user = obj.delivery_partner
        try:
            partner = user.delivery_profile
            return {
                "id": str(partner.id),
                "name": user.get_full_name() or user.username,
                "phone": user.phone,
                "vehicle_type": partner.vehicle_type,
                "vehicle_number": partner.vehicle_number,
                "average_rating": str(partner.average_rating),
            }
        except Exception:
            return {"id": str(user.id), "name": user.get_full_name() or user.username}

    def get_assignment_status(self, obj) -> str | None:
        """Return the current delivery assignment status, or ``None``.

        Args:
            obj: The ``Order`` instance.

        Returns:
            Assignment status string, or ``None`` if no assignment exists.
        """
        try:
            return obj.assignment.status
        except Exception:
            return None

    def get_invoice_id(self, obj):
        """Return the UUID of the first invoice for this order, or ``None``.

        Args:
            obj: The ``Order`` instance.

        Returns:
            Invoice UUID, or ``None``.
        """
        try:
            return obj.invoices.first().id
        except Exception:
            return None

    def get_has_rating(self, obj) -> bool:
        """Return whether this order has been rated by the customer.

        Args:
            obj: The ``Order`` instance.

        Returns:
            ``True`` if a rating exists, ``False`` otherwise.
        """
        return hasattr(obj, "rating")


class OrderRatingSerializer(serializers.ModelSerializer):
    """Serializer for submitting and reading an order rating."""

    class Meta:
        model = OrderRating
        fields = ["id", "order", "rating", "created_at"]
        read_only_fields = ["id", "order", "created_at"]

    def validate_rating(self, value: int) -> int:
        """Ensure the rating is between 1 and 5.

        Args:
            value: The submitted rating integer.

        Returns:
            The validated rating.

        Raises:
            ValidationError: If the value is outside the 1–5 range.
        """
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value


class CouponSerializer(serializers.ModelSerializer):
    """Serializer for coupon codes, including vendor name for display."""

    vendor_name = serializers.CharField(
        source="vendor.store_name", read_only=True, allow_null=True
    )

    class Meta:
        model = Coupon
        fields = [
            "id", "code", "title", "description", "discount_type", "discount_value",
            "min_order_amount", "max_discount_amount", "vendor", "vendor_name",
            "is_active", "usage_limit", "per_user_limit", "used_count",
            "valid_from", "valid_until", "created_at",
        ]
        read_only_fields = ["id", "used_count", "created_at", "vendor_name"]


class IssueMessageSerializer(serializers.ModelSerializer):
    """Serializer for a message thread entry on an order issue."""

    sender_name = serializers.CharField(source="sender.get_full_name", read_only=True)
    sender_username = serializers.CharField(source="sender.username", read_only=True)

    class Meta:
        model = IssueMessage
        fields = [
            "id", "sender", "sender_name", "sender_username",
            "is_admin", "message", "created_at",
        ]
        read_only_fields = [
            "id", "sender", "sender_name", "sender_username", "is_admin", "created_at",
        ]


class OrderIssueSerializer(serializers.ModelSerializer):
    """Full serializer for an order issue with nested message thread."""

    messages = IssueMessageSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.get_full_name", read_only=True)
    customer_username = serializers.CharField(source="customer.username", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    issue_type_display = serializers.CharField(source="get_issue_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = OrderIssue
        fields = [
            "id", "order", "order_number", "customer", "customer_name", "customer_username",
            "issue_type", "issue_type_display", "description", "status", "status_display",
            "admin_notes", "refund_amount", "refund_method", "resolved_by", "resolved_at",
            "created_at", "updated_at", "messages",
        ]
        read_only_fields = [
            "id", "customer", "customer_name", "customer_username", "order_number",
            "issue_type_display", "status_display", "resolved_by", "resolved_at",
            "created_at", "updated_at",
        ]


class CreateOrderSerializer(serializers.Serializer):
    """Write serializer for placing a new order from the cart."""

    delivery_address_id = serializers.UUIDField()
    payment_method = serializers.ChoiceField(choices=["cod"], default="cod")
    notes = serializers.CharField(required=False, default="", allow_blank=True)
    coupon_code = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_delivery_address_id(self, value):
        """Verify the delivery address belongs to the requesting user.

        Args:
            value: UUID of the delivery address.

        Returns:
            The validated address UUID.

        Raises:
            ValidationError: If the address is not found for this user.
        """
        from accounts.models import Address
        user = self.context["request"].user
        try:
            Address.objects.get(id=value, user=user)
        except Address.DoesNotExist:
            raise serializers.ValidationError("Address not found.")
        return value
