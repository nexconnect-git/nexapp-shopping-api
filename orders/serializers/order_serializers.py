"""Serializers for order-related models."""

from rest_framework import serializers

from accounts.models import Address
from accounts.serializers import AddressSerializer
from orders.models import Order, OrderItem, OrderTracking, OrderRating


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
            "coupon_discount", "wallet_discount", "total",
            "notes", "pickup_otp", "delivery_otp", "delivery_photo",
            "estimated_delivery_time", "actual_delivery_time",
            "delivery_latitude", "delivery_longitude", "delivery_tip",
            "vendor_payout", "delivery_payout",
            "is_payment_verified", "razorpay_refund_id", "refund_status",
            "scheduled_for",
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


class CreateOrderSerializer(serializers.Serializer):
    """Write serializer for placing a new order from the cart."""

    delivery_address_id = serializers.UUIDField()
    payment_method = serializers.ChoiceField(choices=["cod", "razorpay"], default="cod")
    notes = serializers.CharField(required=False, default="", allow_blank=True)
    coupon_code = serializers.CharField(required=False, allow_blank=True, default="")
    wallet_amount = serializers.DecimalField(required=False, default=0, max_digits=12, decimal_places=2, min_value=0)
    loyalty_points = serializers.IntegerField(required=False, default=0, min_value=0)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True, default=None)
    # Optional: pre-verified Razorpay payment proof (from the new initiate-first flow)
    razorpay_order_id = serializers.CharField(required=False, allow_blank=True, default="")
    razorpay_payment_id = serializers.CharField(required=False, allow_blank=True, default="")
    razorpay_signature = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_delivery_address_id(self, value):
        """Verify the delivery address belongs to the requesting user.

        Args:
            value: UUID of the delivery address.

        Returns:
            The validated address UUID.

        Raises:
            ValidationError: If the address is not found for this user.
        """
        user = self.context["request"].user
        try:
            Address.objects.get(id=value, user=user)
        except Address.DoesNotExist:
            raise serializers.ValidationError("Address not found.")
        return value
