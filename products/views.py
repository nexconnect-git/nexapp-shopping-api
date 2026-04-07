"""Views for the products app.

Covers public product/category browsing, vendor product image management,
AI placeholder image generation, stock management, and admin product/category
CRUD.
"""

import io
import uuid as _uuid

from PIL import Image as PILImage, ImageDraw
from django.core.files.base import ContentFile
from django.db.models import F

from rest_framework import viewsets, generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from accounts.permissions import IsAdminRole, IsApprovedVendor
from backend.mixins import BaseDetailView
from products.models import Category, Product, ProductImage, ProductReview
from products.serializers import (
    CategorySerializer,
    ProductSerializer,
    ProductListSerializer,
    ProductCreateUpdateSerializer,
    ProductReviewSerializer,
    ProductImageSerializer,
)
from products.services import ProductService
from vendors.models import Vendor


class CategoryListView(generics.ListAPIView):
    """GET /api/products/categories/ — list all active root categories."""

    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    queryset = Category.objects.filter(is_active=True, parent__isnull=True)


class ProductListView(generics.ListAPIView):
    """GET /api/products/ — list products with optional filters."""

    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        """Return filtered product queryset based on query parameters.

        Supported filters: ``category``, ``vendor``, ``search``,
        ``min_price``, ``max_price``, ``is_available``.
        """
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
    """GET /api/products/<pk>/ — single product detail."""

    permission_classes = [AllowAny]
    serializer_class = ProductSerializer
    queryset = Product.objects.select_related("vendor", "category").prefetch_related(
        "images", "reviews"
    )


class FeaturedProductsView(generics.ListAPIView):
    """GET /api/products/featured/ — list featured, available products."""

    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer
    queryset = Product.objects.filter(is_featured=True, is_available=True)


class ProductReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for product reviews; write actions require authentication."""

    serializer_class = ProductReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return reviews scoped to a product when ``product_id`` is in kwargs."""
        product_id = self.kwargs.get("product_id")
        if product_id:
            return ProductReview.objects.filter(product_id=product_id)
        return ProductReview.objects.all()

    def get_permissions(self):
        """Allow unauthenticated reads; require auth for mutations."""
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        """Attach the requesting user as the review author."""
        serializer.save(customer=self.request.user)


# ── Admin views ─────────────────────────────────────────────────────────────

class AdminPagination(PageNumberPagination):
    """Default 20-items-per-page pagination for admin views."""

    page_size = 20


class AdminCategoryListCreateView(APIView):
    """GET/POST /api/admin/categories/"""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        """Return categories, optionally scoped by ``parent`` query param.

        Args:
            request: Authenticated admin DRF request.

        Returns:
            200 with list of serialised categories.
        """
        parent_param = request.query_params.get("parent")
        if parent_param == "root":
            qs = Category.objects.filter(
                parent__isnull=True
            ).order_by("display_order", "name")
        elif parent_param:
            qs = Category.objects.filter(
                parent_id=parent_param
            ).order_by("display_order", "name")
        else:
            qs = Category.objects.all().order_by("display_order", "name")
        return Response(CategorySerializer(qs, many=True).data)

    def post(self, request):
        """Create a new category.

        Args:
            request: Authenticated admin DRF request with category data.

        Returns:
            201 with created category data.
        """
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminCategoryDetailView(BaseDetailView, APIView):
    """GET/PATCH/DELETE /api/admin/categories/<pk>/"""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get_category(self, pk):
        """Look up a Category by PK via the BaseDetailView mixin.

        Args:
            pk: UUID primary key of the category.

        Returns:
            ``Category`` or ``None``.
        """
        return self.get_object_or_none(Category, pk=pk)

    def get(self, request, pk):  # noqa: ARG002
        """Return a single category.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key.

        Returns:
            200 with category data, or 404.
        """
        category = self._get_category(pk)
        if not category:
            return Response(
                {"error": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(CategorySerializer(category).data)

    def patch(self, request, pk):
        """Partially update a category.

        Args:
            request: Authenticated admin DRF request with fields to update.
            pk: UUID primary key.

        Returns:
            200 with updated data, or 404.
        """
        category = self._get_category(pk)
        if not category:
            return Response(
                {"error": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = CategorySerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):  # noqa: ARG002
        """Delete a category.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key.

        Returns:
            204 on success, or 404.
        """
        category = self._get_category(pk)
        if not category:
            return Response(
                {"error": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminProductListCreateView(APIView):
    """GET/POST /api/admin/products/"""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        """Return a paginated, filterable product list.

        Query params: ``search``, ``vendor``, ``category``.

        Args:
            request: Authenticated admin DRF request.

        Returns:
            Paginated product list.
        """
        qs = (
            Product.objects.select_related("vendor", "category")
            .prefetch_related("images")
            .order_by("-created_at")
        )
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(name__icontains=search)
        vendor = request.query_params.get("vendor")
        if vendor:
            qs = qs.filter(vendor_id=vendor)
        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category__slug=category)
        paginator = AdminPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            ProductListSerializer(
                page, many=True, context={"request": request}
            ).data
        )

    def post(self, request):
        """Create a product on behalf of a vendor (admin must supply vendor_id).

        Args:
            request: Authenticated admin DRF request.

        Returns:
            201 with product data, or 400/404.
        """
        serializer = ProductCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendor_id = request.data.get("vendor_id")
        if not vendor_id:
            return Response(
                {"error": "vendor_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            vendor = Vendor.objects.get(pk=vendor_id)
        except Vendor.DoesNotExist:
            return Response(
                {"error": "Vendor not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer.save(vendor=vendor)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminProductDetailView(BaseDetailView, APIView):
    """GET/PATCH/DELETE /api/admin/products/<pk>/"""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get_product(self, pk):
        """Look up a Product with related vendor/category via the mixin.

        Args:
            pk: UUID primary key.

        Returns:
            ``Product`` with select_related applied, or ``None``.
        """
        try:
            return Product.objects.select_related("vendor", "category").get(pk=pk)
        except Product.DoesNotExist:
            return None

    def get(self, request, pk):  # noqa: ARG002
        """Return a single product.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key.

        Returns:
            200 with product data, or 404.
        """
        product = self._get_product(pk)
        if not product:
            return Response(
                {"error": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(ProductSerializer(product).data)

    def patch(self, request, pk):
        """Partially update a product.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key.

        Returns:
            200 with updated data, or 404.
        """
        product = self._get_product(pk)
        if not product:
            return Response(
                {"error": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = ProductCreateUpdateSerializer(
            product, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):  # noqa: ARG002
        """Delete a product.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key.

        Returns:
            204 on success, or 404.
        """
        product = self._get_product(pk)
        if not product:
            return Response(
                {"error": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )
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
        """Return the product if it belongs to the given vendor, else None.

        Args:
            pk: UUID primary key of the product.
            vendor: The requesting vendor profile.

        Returns:
            ``Product`` or ``None``.
        """
        try:
            return Product.objects.get(pk=pk, vendor=vendor)
        except Product.DoesNotExist:
            return None

    def get(self, request, pk):
        """List all images for a vendor's product.

        Args:
            request: Authenticated vendor DRF request.
            pk: UUID primary key of the product.

        Returns:
            200 with list of image data, or 404.
        """
        vendor = request.user.vendor_profile
        product = self._get_product(pk, vendor)
        if not product:
            return Response(
                {"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND
            )
        images = product.images.all()
        return Response(
            ProductImageSerializer(
                images, many=True, context={"request": request}
            ).data
        )

    def post(self, request, pk):
        """Upload an image for a vendor's product.

        Args:
            request: Authenticated vendor DRF request with ``image`` file,
                optional ``is_primary`` and ``is_ai_generated`` fields.
            pk: UUID primary key of the product.

        Returns:
            201 with image data, or 400/404.
        """
        vendor = request.user.vendor_profile
        image_file = request.FILES.get("image")
        if not image_file:
            return Response(
                {"error": "image file is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_primary = request.data.get("is_primary", "false").lower() == "true"
        is_ai = request.data.get("is_ai_generated", "false").lower() == "true"

        try:
            product_image = ProductService.add_image_to_product(
                str(pk), str(vendor.id), image_file, is_primary, is_ai
            )
            return Response(
                ProductImageSerializer(
                    product_image, context={"request": request}
                ).data,
                status=status.HTTP_201_CREATED,
            )
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class VendorProductImageDetailView(APIView):
    """DELETE /api/vendors/products/<pk>/images/<img_pk>/"""

    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def delete(self, request, pk, img_pk):
        """Delete a product image, promoting the next image to primary if needed.

        Args:
            request: Authenticated vendor DRF request.
            pk: UUID primary key of the product.
            img_pk: UUID primary key of the image.

        Returns:
            204 on success, or 404.
        """
        vendor = request.user.vendor_profile
        try:
            product = Product.objects.get(pk=pk, vendor=vendor)
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND
            )
        try:
            product_image = ProductImage.objects.get(pk=img_pk, product=product)
        except ProductImage.DoesNotExist:
            return Response(
                {"error": "Image not found."}, status=status.HTTP_404_NOT_FOUND
            )

        was_primary = product_image.is_primary
        product_image.image.delete(save=False)
        product_image.delete()

        # Promote the next image to primary when the primary was deleted
        if was_primary:
            remaining = product.images.first()
            if remaining:
                remaining.is_primary = True
                remaining.save(update_fields=["is_primary"])

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
    """Create a styled 512×512 placeholder PNG using Pillow.

    Selects a background colour deterministically from ``prompt`` via MD5,
    draws a subtle grid overlay, and renders the prompt text as a label.

    Args:
        prompt: Text prompt used to seed the colour selection and label.

    Returns:
        Raw PNG bytes of the generated image.
    """
    import hashlib
    import textwrap

    color_idx = int(hashlib.md5(prompt.encode()).hexdigest(), 16) % len(PALETTE)
    bg_color = PALETTE[color_idx]
    img = PILImage.new("RGB", (512, 512), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Subtle grid overlay using a slightly darker shade of the bg colour
    for x in range(0, 512, 32):
        draw.line(
            [(x, 0), (x, 512)],
            fill=(*bg_color[:2], max(0, bg_color[2] - 30)),
            width=1,
        )
    for y in range(0, 512, 32):
        draw.line(
            [(0, y), (512, y)],
            fill=(*bg_color[:2], max(0, bg_color[2] - 30)),
            width=1,
        )

    draw.rectangle([(40, 200), (472, 312)], fill=(0, 0, 0, 120))
    label = textwrap.fill(f"AI: {prompt[:60]}", width=30)
    draw.text((256, 240), label, fill="white", anchor="mm")
    draw.text((256, 296), "✦ AI Generated ✦", fill=(220, 220, 255), anchor="mm")

    image_buffer = io.BytesIO()
    img.save(image_buffer, format="PNG")
    return image_buffer.getvalue()


class AIImageGenerateView(APIView):
    """POST /api/products/ai-image/ — generate a placeholder image from a prompt."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request):
        """Generate a placeholder image and attach it to a product.

        Args:
            request: Authenticated vendor DRF request with ``prompt`` and
                ``product_id`` fields.

        Returns:
            201 with image data, or 400/404.
        """
        prompt = request.data.get("prompt", "").strip()
        product_id = request.data.get("product_id")
        if not prompt:
            return Response(
                {"error": "prompt is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not product_id:
            return Response(
                {"error": "product_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        vendor = request.user.vendor_profile
        png_bytes = _make_placeholder_image(prompt)
        filename = f"ai_{_uuid.uuid4().hex[:8]}.png"
        content_file = ContentFile(png_bytes, name=filename)

        try:
            product_image = ProductService.add_image_to_product(
                str(product_id),
                str(vendor.id),
                content_file,
                is_primary=False,
                is_ai_generated=True,
            )
            return Response(
                ProductImageSerializer(
                    product_image, context={"request": request}
                ).data,
                status=status.HTTP_201_CREATED,
            )
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ── Vendor Stock Management Views ─────────────────────────────────────────────

class VendorStockUpdateView(APIView):
    """PATCH /api/vendors/products/<pk>/stock/"""

    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def patch(self, request, pk):
        """Update stock level and/or low-stock threshold for a product.

        Args:
            request: Authenticated vendor DRF request with optional ``stock``
                and ``low_stock_threshold`` fields.
            pk: UUID primary key of the product.

        Returns:
            200 with updated stock info, or 404.
        """
        vendor = request.user.vendor_profile
        stock = request.data.get("stock")
        if stock is not None:
            stock = int(stock)
        threshold = request.data.get("low_stock_threshold")
        if threshold is not None:
            threshold = int(threshold)

        try:
            product = ProductService.update_stock(
                str(pk), str(vendor.id), stock, threshold
            )
            return Response(
                {
                    "id": str(product.id),
                    "stock": product.stock,
                    "low_stock_threshold": product.low_stock_threshold,
                }
            )
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND
            )


class VendorLowStockView(generics.ListAPIView):
    """GET /api/vendors/products/low-stock/"""

    permission_classes = [IsAuthenticated, IsApprovedVendor]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        """Return products whose stock is at or below their alert threshold."""
        vendor = self.request.user.vendor_profile
        return Product.objects.filter(
            vendor=vendor,
            stock__lte=F("low_stock_threshold"),
        ).order_by("stock")
