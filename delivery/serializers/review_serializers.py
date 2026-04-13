from rest_framework import serializers

from delivery.models import DeliveryReview


class DeliveryReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)

    class Meta:
        model = DeliveryReview
        fields = ['id', 'delivery_partner', 'customer', 'customer_name', 'order',
                  'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'customer', 'created_at']

    def create(self, validated_data):
        validated_data['customer'] = self.context['request'].user
        return super().create(validated_data)
