from rest_framework import serializers

from products.models import ProductReview


class ProductReviewSerializer(serializers.ModelSerializer):
    """Serializer for ProductReview with read-only customer name."""

    customer_name = serializers.CharField(
        source="customer.get_full_name", read_only=True
    )

    class Meta:
        model = ProductReview
        fields = [
            "id", "product", "customer", "customer_name", "rating",
            "comment", "created_at",
        ]
        read_only_fields = ["id", "customer", "created_at"]

    def create(self, validated_data):
        """Attach the requesting user as the review author on creation."""
        validated_data["customer"] = self.context["request"].user
        return super().create(validated_data)
