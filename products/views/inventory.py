from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from accounts.permissions import IsApprovedVendor
from helpers.cache_helpers import cached_api_response
from backend.actions.customer_flow.fulfillment_filters import (
    active_fulfillment_node_for_request,
    filter_products_for_fulfillment_node,
    filter_products_for_serviceable_vendors,
    request_address_from_query,
    should_enforce_fulfillment_node_for_request,
)
from products.serializers.product_serializers import ProductSerializer, ProductListSerializer
from products.serializers.image_serializers import ProductImageSerializer
from products.data.product_repository import ProductRepository
from products.data.image_repository import ProductImageRepository
from products.actions.inventory import AddProductImageAction, UpdateStockAction
from products.actions.approval import ProductApprovalPolicy
from products.models import Product

class ProductListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer

    def list(self, request, *args, **kwargs):
        return cached_api_response(
            request,
            'products:list',
            120,
            lambda: super(ProductListView, self).list(request, *args, **kwargs),
            include_user=False,
        )

    def get_queryset(self):
        queryset = ProductRepository.filter(
            search=self.request.query_params.get("search"),
            category=self.request.query_params.get("category"),
            vendor=self.request.query_params.get("vendor"),
            min_price=self.request.query_params.get("min_price"),
            max_price=self.request.query_params.get("max_price"),
            is_available=True
        )
        return _filter_customer_products_for_request(self.request, queryset)

class FeaturedProductsView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer

    def list(self, request, *args, **kwargs):
        return cached_api_response(
            request,
            'products:featured',
            120,
            lambda: super(FeaturedProductsView, self).list(request, *args, **kwargs),
            include_user=False,
        )

    def get_queryset(self):
        queryset = ProductRepository.get_featured()
        return _filter_customer_products_for_request(self.request, queryset)

class ProductDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer

    def retrieve(self, request, *args, **kwargs):
        return cached_api_response(
            request,
            f'products:detail:{kwargs.get("pk")}',
            120,
            lambda: super(ProductDetailView, self).retrieve(request, *args, **kwargs),
            include_user=False,
        )

    def get_queryset(self):
        queryset = ProductRepository.get_all()
        return _filter_customer_products_for_request(self.request, queryset)


def _filter_customer_products_for_request(request, queryset):
    fulfillment_node = active_fulfillment_node_for_request(request)
    if fulfillment_node:
        return filter_products_for_fulfillment_node(queryset, fulfillment_node)
    if should_enforce_fulfillment_node_for_request(request):
        return queryset.none()
    address = request_address_from_query(request)
    if address:
        return filter_products_for_serviceable_vendors(queryset, address)
    return queryset

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
            product = img.product
            ProductImageRepository.delete(img)
            if product.approval_status in {
                Product.APPROVAL_STATUS_APPROVED,
                Product.APPROVAL_STATUS_REJECTED,
                Product.APPROVAL_STATUS_PENDING,
            }:
                update_fields = ProductApprovalPolicy.mark_requires_review(product, ["images"])
                update_fields.append("updated_at")
                product.save(update_fields=sorted(set(update_fields)))
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
