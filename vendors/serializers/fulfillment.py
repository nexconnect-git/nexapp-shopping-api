from rest_framework import serializers

from vendors.models import (
    FulfillmentNode,
    FulfillmentNodeInventory,
    FulfillmentNodeServiceArea,
)


class FulfillmentNodeSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.store_name", read_only=True)

    class Meta:
        model = FulfillmentNode
        fields = [
            "id",
            "vendor",
            "vendor_name",
            "code",
            "name",
            "node_type",
            "status",
            "is_accepting_orders",
            "address",
            "city",
            "state",
            "postal_code",
            "latitude",
            "longitude",
            "instant_radius_km",
            "max_delivery_radius_km",
            "base_prep_time_min",
            "delivery_time_per_km_min",
            "daily_order_capacity",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "vendor_name", "created_at", "updated_at"]

    def validate(self, attrs):
        node_type = attrs.get("node_type", getattr(self.instance, "node_type", "vendor_store"))
        vendor = attrs.get("vendor", getattr(self.instance, "vendor", None))
        if node_type == "vendor_store" and vendor is None:
            raise serializers.ValidationError({"vendor": "Vendor store nodes must be linked to a vendor."})
        return attrs


class FulfillmentNodeServiceAreaSerializer(serializers.ModelSerializer):
    node_name = serializers.CharField(source="node.name", read_only=True)

    class Meta:
        model = FulfillmentNodeServiceArea
        fields = [
            "id",
            "node",
            "node_name",
            "label",
            "city",
            "state",
            "postal_code",
            "center_latitude",
            "center_longitude",
            "radius_km",
            "is_active",
            "priority",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "node_name", "created_at", "updated_at"]


class FulfillmentNodeInventorySerializer(serializers.ModelSerializer):
    node_name = serializers.CharField(source="node.name", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    sellable_stock = serializers.IntegerField(read_only=True)

    class Meta:
        model = FulfillmentNodeInventory
        fields = [
            "id",
            "node",
            "node_name",
            "product",
            "product_name",
            "product_sku",
            "stock",
            "reserved_stock",
            "sellable_stock",
            "low_stock_threshold",
            "is_available",
            "updated_at",
        ]
        read_only_fields = ["id", "node_name", "product_name", "product_sku", "sellable_stock", "updated_at"]

    def validate(self, attrs):
        stock = attrs.get("stock", getattr(self.instance, "stock", 0))
        reserved_stock = attrs.get("reserved_stock", getattr(self.instance, "reserved_stock", 0))
        if reserved_stock < 0 or stock < 0:
            raise serializers.ValidationError("Stock values cannot be negative.")
        if reserved_stock > stock:
            raise serializers.ValidationError({"reserved_stock": "Reserved stock cannot exceed total stock."})
        return attrs
