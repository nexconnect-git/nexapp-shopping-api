import io
import os
import uuid as _uuid
from PIL import Image as PILImage, ImageDraw, ImageFont

from django.core.files.base import ContentFile
from rest_framework import viewsets, generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from accounts.permissions import IsAdminRole, IsApprovedVendor
from .models import Category, Product, ProductImage, ProductReview
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    ProductListSerializer,
    ProductCreateUpdateSerializer,
    ProductReviewSerializer,
    ProductImageSerializer,
)


class CategoryListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    queryset = Category.objects.filter(is_active=True, parent__isnull=True)


class ProductListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        qs = Product.objects.select_related("vendor", "category").prefetch_related(
            "images"
        )
        category = self.request.query_params.get("category")
        vendor = self.request.query_params.get("vendor")
        search = self.request.query_params.get("search")
        min_price = self.request.query_params.get("min_price")
        max_price = self.request.query_params.get("max_price")
        is_available = self.request.query_params.get("is_available")

        if category:
            qs = qs.filter(category__slug=category)
        if vendor:
            qs = qs.filter(vendor_id=vendor)
        if search:
            qs = qs.filter(name__icontains=search)
        if min_price:
            qs = qs.filter(price__gte=min_price)
        if max_price:
            qs = qs.filter(price__lte=max_price)
        if is_available is not None:
            qs = qs.filter(is_available=is_available.lower() == "true")
        return qs


class ProductDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer
    queryset = Product.objects.select_related("vendor", "category").prefetch_related(
        "images", "reviews"
    )


class FeaturedProductsView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer
    queryset = Product.objects.filter(is_featured=True, is_available=True)


class ProductReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ProductReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        product_id = self.kwargs.get("product_id")
        if product_id:
            return ProductReview.objects.filter(product_id=product_id)
        return ProductReview.objects.all()

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)


# ── Admin views ─────────────────────────────────────────────────────────────

class AdminPagination(PageNumberPagination):
    page_size = 20


class AdminCategoryListCreateView(APIView):
    """GET/POST /api/admin/categories/"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        parent_param = request.query_params.get('parent')
        if parent_param == 'root':
            qs = Category.objects.filter(parent__isnull=True).order_by('display_order', 'name')
        elif parent_param:
            qs = Category.objects.filter(parent_id=parent_param).order_by('display_order', 'name')
        else:
            qs = Category.objects.all().order_by('display_order', 'name')
        return Response(CategorySerializer(qs, many=True).data)

    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminCategoryDetailView(APIView):
    """GET/PATCH/DELETE /api/admin/categories/<pk>/"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get(self, pk):
        try:
            return Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return None

    def get(self, request, pk):
        cat = self._get(pk)
        if not cat:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(CategorySerializer(cat).data)

    def patch(self, request, pk):
        cat = self._get(pk)
        if not cat:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CategorySerializer(cat, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        cat = self._get(pk)
        if not cat:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        cat.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminProductListCreateView(APIView):
    """GET/POST /api/admin/products/"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        qs = Product.objects.select_related('vendor', 'category').prefetch_related('images').order_by('-created_at')
        search = request.query_params.get('search')
        if search:
            qs = qs.filter(name__icontains=search)
        vendor = request.query_params.get('vendor')
        if vendor:
            qs = qs.filter(vendor_id=vendor)
        category = request.query_params.get('category')
        if category:
            qs = qs.filter(category__slug=category)
        paginator = AdminPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(ProductListSerializer(page, many=True, context={'request': request}).data)

    def post(self, request):
        serializer = ProductCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # admin must supply vendor_id explicitly
        vendor_id = request.data.get('vendor_id')
        if not vendor_id:
            return Response({'error': 'vendor_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        from vendors.models import Vendor
        try:
            vendor = Vendor.objects.get(pk=vendor_id)
        except Vendor.DoesNotExist:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer.save(vendor=vendor)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminProductDetailView(APIView):
    """GET/PATCH/DELETE /api/admin/products/<pk>/"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get(self, pk):
        try:
            return Product.objects.select_related('vendor', 'category').get(pk=pk)
        except Product.DoesNotExist:
            return None

    def get(self, request, pk):
        product = self._get(pk)
        if not product:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProductSerializer(product).data)

    def patch(self, request, pk):
        product = self._get(pk)
        if not product:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProductCreateUpdateSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        product = self._get(pk)
        if not product:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Vendor Product Image Views ───────────────────────────────────────────────

MAX_PRODUCT_IMAGES = 5
MAX_AI_IMAGES = 2


class VendorProductImagesView(APIView):
    """GET/POST /api/vendors/products/<pk>/images/"""
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    parser_classes = [MultiPartParser, FormParser]

    def _get_product(self, pk, vendor):
        try:
            return Product.objects.get(pk=pk, vendor=vendor)
        except Product.DoesNotExist:
            return None

    def get(self, request, pk):
        vendor = request.user.vendor_profile
        product = self._get_product(pk, vendor)
        if not product:
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)
        images = product.images.all()
        return Response(ProductImageSerializer(images, many=True, context={'request': request}).data)

    def post(self, request, pk):
        vendor = request.user.vendor_profile
        product = self._get_product(pk, vendor)
        if not product:
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        existing_count = product.images.count()
        if existing_count >= MAX_PRODUCT_IMAGES:
            return Response(
                {'error': f'Maximum {MAX_PRODUCT_IMAGES} images allowed per product.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_ai = request.data.get('is_ai_generated', 'false').lower() == 'true'
        if is_ai:
            ai_count = product.images.filter(is_ai_generated=True).count()
            if ai_count >= MAX_AI_IMAGES:
                return Response(
                    {'error': f'Maximum {MAX_AI_IMAGES} AI-generated images allowed per product.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'error': 'image file is required.'}, status=status.HTTP_400_BAD_REQUEST)

        is_primary = request.data.get('is_primary', 'false').lower() == 'true'
        if is_primary:
            product.images.filter(is_primary=True).update(is_primary=False)

        img = ProductImage.objects.create(
            product=product,
            image=image_file,
            is_primary=is_primary or existing_count == 0,
            is_ai_generated=is_ai,
            display_order=existing_count,
        )
        return Response(
            ProductImageSerializer(img, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class VendorProductImageDetailView(APIView):
    """DELETE /api/vendors/products/<pk>/images/<img_pk>/"""
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def delete(self, request, pk, img_pk):
        vendor = request.user.vendor_profile
        try:
            product = Product.objects.get(pk=pk, vendor=vendor)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            img = ProductImage.objects.get(pk=img_pk, product=product)
        except ProductImage.DoesNotExist:
            return Response({'error': 'Image not found.'}, status=status.HTTP_404_NOT_FOUND)

        was_primary = img.is_primary
        img.image.delete(save=False)
        img.delete()

        if was_primary:
            remaining = product.images.first()
            if remaining:
                remaining.is_primary = True
                remaining.save(update_fields=['is_primary'])

        return Response(status=status.HTTP_204_NO_CONTENT)


# ── AI Image Generation (Stub) ────────────────────────────────────────────────

PALETTE = [
    (99, 102, 241),   # indigo
    (16, 185, 129),   # emerald
    (245, 158, 11),   # amber
    (239, 68, 68),    # red
    (59, 130, 246),   # blue
]


def _make_placeholder_image(prompt: str) -> bytes:
    """Create a styled 512x512 placeholder image using Pillow."""
    import hashlib, textwrap
    color_idx = int(hashlib.md5(prompt.encode()).hexdigest(), 16) % len(PALETTE)
    bg_color = PALETTE[color_idx]
    img = PILImage.new('RGB', (512, 512), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Subtle grid overlay
    for x in range(0, 512, 32):
        draw.line([(x, 0), (x, 512)], fill=(*bg_color[:2], max(0, bg_color[2] - 30)), width=1)
    for y in range(0, 512, 32):
        draw.line([(0, y), (512, y)], fill=(*bg_color[:2], max(0, bg_color[2] - 30)), width=1)

    # Label
    draw.rectangle([(40, 200), (472, 312)], fill=(0, 0, 0, 120))
    label = textwrap.fill(f"AI: {prompt[:60]}", width=30)
    draw.text((256, 240), label, fill='white', anchor='mm')
    draw.text((256, 296), '✦ AI Generated ✦', fill=(220, 220, 255), anchor='mm')

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


class AIImageGenerateView(APIView):
    """POST /api/products/ai-image/  — Generates a placeholder image from a text prompt."""
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request):
        prompt = request.data.get('prompt', '').strip()
        product_id = request.data.get('product_id')
        if not prompt:
            return Response({'error': 'prompt is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not product_id:
            return Response({'error': 'product_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        vendor = request.user.vendor_profile
        try:
            product = Product.objects.get(pk=product_id, vendor=vendor)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        existing_count = product.images.count()
        if existing_count >= MAX_PRODUCT_IMAGES:
            return Response(
                {'error': f'Maximum {MAX_PRODUCT_IMAGES} images allowed per product.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ai_count = product.images.filter(is_ai_generated=True).count()
        if ai_count >= MAX_AI_IMAGES:
            return Response(
                {'error': f'Maximum {MAX_AI_IMAGES} AI-generated images per product.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        png_bytes = _make_placeholder_image(prompt)
        filename = f'ai_{_uuid.uuid4().hex[:8]}.png'
        content_file = ContentFile(png_bytes, name=filename)

        img = ProductImage.objects.create(
            product=product,
            image=content_file,
            is_primary=existing_count == 0,
            is_ai_generated=True,
            display_order=existing_count,
        )
        return Response(
            ProductImageSerializer(img, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


# ── Vendor Stock Management Views ─────────────────────────────────────────────

class VendorStockUpdateView(APIView):
    """PATCH /api/vendors/products/<pk>/stock/"""
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def patch(self, request, pk):
        vendor = request.user.vendor_profile
        try:
            product = Product.objects.get(pk=pk, vendor=vendor)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        stock = request.data.get('stock')
        threshold = request.data.get('low_stock_threshold')

        if stock is not None:
            product.stock = int(stock)
        if threshold is not None:
            product.low_stock_threshold = int(threshold)
        product.save(update_fields=['stock', 'low_stock_threshold', 'updated_at'])
        return Response({'id': str(product.id), 'stock': product.stock,
                         'low_stock_threshold': product.low_stock_threshold})


class VendorLowStockView(generics.ListAPIView):
    """GET /api/vendors/products/low-stock/"""
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        vendor = self.request.user.vendor_profile
        from django.db.models import F
        return Product.objects.filter(
            vendor=vendor,
            stock__lte=F('low_stock_threshold'),
        ).order_by('stock')

