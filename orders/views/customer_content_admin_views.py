from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from orders.data.customer_content_repo import CustomerContentBlockRepository
from orders.models import CustomerContentBlock


class CustomerContentBlockSerializer(serializers.ModelSerializer):
    placement_label = serializers.CharField(source='get_placement_display', read_only=True)
    template_label = serializers.CharField(source='get_template_display', read_only=True)

    class Meta:
        model = CustomerContentBlock
        fields = [
            'id',
            'placement',
            'placement_label',
            'template',
            'template_label',
            'eyebrow',
            'title',
            'subtitle',
            'cta_label',
            'cta_url',
            'icon',
            'tone',
            'image',
            'display_order',
            'is_active',
            'starts_at',
            'ends_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        starts_at = attrs.get('starts_at', getattr(self.instance, 'starts_at', None))
        ends_at = attrs.get('ends_at', getattr(self.instance, 'ends_at', None))
        if starts_at and ends_at and starts_at > ends_at:
            raise serializers.ValidationError({'ends_at': 'End time must be after start time.'})
        return attrs


class AdminCustomerContentBlockListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        blocks = CustomerContentBlockRepository().get_all_ordered()
        return Response(CustomerContentBlockSerializer(blocks, many=True).data)

    def post(self, request):
        serializer = CustomerContentBlockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminCustomerContentBlockDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get_object(self, pk):
        return CustomerContentBlockRepository().get_by_id(pk)

    def get(self, request, pk):
        block = self._get_object(pk)
        if not block:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(CustomerContentBlockSerializer(block).data)

    def patch(self, request, pk):
        block = self._get_object(pk)
        if not block:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CustomerContentBlockSerializer(block, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        block = self._get_object(pk)
        if not block:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        block.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
