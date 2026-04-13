from rest_framework import status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import models

from accounts.permissions import IsAdminRole
from products.models import Category, Product
from products.serializers import CategorySerializer, ProductSerializer
from products.serializers.product_serializers import ProductCreateUpdateSerializer, ProductListSerializer

class AdminProductViewSet(viewsets.ModelViewSet):
    """Admin endpoint to manage all products — supports ?search= and ?status= filtering."""
    permission_classes = [IsAuthenticated, IsAdminRole]
    pagination_class = None  # handled client-side via page_size param

    def get_queryset(self):
        qs = Product.objects.select_related('vendor', 'category').order_by('vendor__store_name', '-created_at')
        search = self.request.query_params.get('search')
        status_filter = self.request.query_params.get('status')
        page_size = self.request.query_params.get('page_size')

        if search:
            qs = qs.filter(
                models.Q(name__icontains=search) |
                models.Q(vendor__store_name__icontains=search)
            )
        if status_filter:
            qs = qs.filter(status=status_filter)

        # Re-enable pagination when page_size is specified
        if page_size:
            self.pagination_class = StandardPagination
        return qs

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProductCreateUpdateSerializer
        return ProductListSerializer




class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminCategoryListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        qs = Category.objects.all().order_by("name")
        parent = request.query_params.get("parent")
        
        if parent == "root":
            qs = qs.filter(parent__isnull=True)
        elif parent:
            qs = qs.filter(parent_id=parent)
            
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(CategorySerializer(page, many=True).data)

    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminCategoryDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get_object(self, pk):
        try:
            return Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CategorySerializer(obj).data)

    def patch(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = CategorySerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminProductListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        qs = Product.objects.select_related("vendor", "category").order_by("-created_at")

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(name__icontains=search)

        vendor_id = request.query_params.get("vendor")
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)

        category_id = request.query_params.get("category")
        if category_id:
            qs = qs.filter(category_id=category_id)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(ProductSerializer(page, many=True).data)

    def post(self, request):
        serializer = ProductSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminProductDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get_object(self, pk):
        try:
            return Product.objects.select_related("vendor", "category").get(pk=pk)
        except Product.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProductSerializer(obj).data)

    def patch(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProductSerializer(obj, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
