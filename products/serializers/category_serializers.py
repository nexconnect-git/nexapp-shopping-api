from rest_framework import serializers

from products.models import Category


class CategorySerializer(serializers.ModelSerializer):
    """Full serializer for Category including nested children and metadata."""

    children = serializers.SerializerMethodField()
    parent_name = serializers.SerializerMethodField()
    subcategory_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id", "name", "slug", "description", "image", "parent",
            "parent_name", "is_active", "show_in_customer_ui", "display_order",
            "children", "subcategory_count", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_children(self, obj) -> list:
        """Return serialized active child categories."""
        children = obj.children.filter(is_active=True)
        return CategorySerializer(children, many=True).data

    def get_parent_name(self, obj) -> str | None:
        """Return the parent category's name, or None for root categories."""
        return obj.parent.name if obj.parent else None

    def get_subcategory_count(self, obj) -> int:
        """Return the total number of direct child categories."""
        return obj.children.count()
