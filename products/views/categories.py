from rest_framework import generics
from rest_framework.permissions import AllowAny
from products.serializers.category_serializers import CategorySerializer
from products.data.category_repository import CategoryRepository

class CategoryListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CategorySerializer

    def get_queryset(self):
        return CategoryRepository.get_customer_visible()
