from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from accounts.permissions import IsApprovedVendor
from products.serializers.product_serializers import ProductSerializer, ProductListSerializer
from products.serializers.image_serializers import ProductImageSerializer
from products.data.product_repository import ProductRepository
from products.data.image_repository import ProductImageRepository
from products.actions.inventory import AddProductImageAction, UpdateStockAction

class ProductListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        return ProductRepository.filter(
            search=self.request.query_params.get("search"),
            category=self.request.query_params.get("category"),
            vendor=self.request.query_params.get("vendor"),
            min_price=self.request.query_params.get("min_price"),
            max_price=self.request.query_params.get("max_price"),
            is_available=True
        )

class FeaturedProductsView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        return ProductRepository.get_featured()

class ProductDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer

    def get_queryset(self):
        return ProductRepository.get_all()

class VendorProductImagesView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request, pk):
        product = ProductRepository.get_by_id(pk)
        if not product:
            return Response(status=status.HTTP_404_NOT_FOUND)
        images = ProductImageRepository.get_all(product)
        return Response(ProductImageSerializer(images, many=True).data)

    def post(self, request, pk):
        action = AddProductImageAction()
        is_primary = request.data.get("is_primary", "false").lower() == "true"
        is_ai = request.data.get("is_ai_generated", "false").lower() == "true"
        try:
            image = action.execute(
                product_id=pk,
                vendor_id=request.user.vendor_profile.id,
                image_file=request.FILES.get("image"),
                is_primary=is_primary,
                is_ai_generated=is_ai
            )
            return Response(ProductImageSerializer(image).data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class VendorProductImageDetailView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def delete(self, request, pk, img_pk):
        img = ProductImageRepository.get_by_id(img_pk)
        if img and str(img.product_id) == str(pk) and img.product.vendor_id == request.user.vendor_profile.id:
            ProductImageRepository.delete(img)
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_404_NOT_FOUND)

class VendorStockUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def patch(self, request, pk):
        action = UpdateStockAction()
        try:
            product = action.execute(
                product_id=pk,
                vendor_id=request.user.vendor_profile.id,
                stock=request.data.get("stock"),
                threshold=request.data.get("low_stock_threshold")
            )
            return Response(ProductSerializer(product).data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class VendorLowStockView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        return ProductRepository.get_low_stock(self.request.user.vendor_profile)

class AIImageGenerateView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request):
        return Response({"message": "Placeholder."})
