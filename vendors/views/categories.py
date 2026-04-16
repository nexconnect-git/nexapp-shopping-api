"""Vendor category views — lets approved vendors browse and create categories/subcategories."""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsApprovedVendor
from products.models.category import Category
from products.serializers.category_serializers import CategorySerializer
from products.data.category_repository import CategoryRepository


def _slugify(name: str) -> str:
    """Produce a URL-safe slug from a name, appending a counter if it conflicts."""
    import re
    base = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    slug = base
    counter = 1
    while Category.objects.filter(slug=slug).exists():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


class VendorCategoryListCreateView(APIView):
    """
    GET  /api/vendors/categories/         — list all root categories with nested children
    POST /api/vendors/categories/         — create a new root category (show_in_customer_ui=False until admin approves)
    """
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request):
        cats = Category.objects.filter(is_active=True, parent__isnull=True).order_by('display_order', 'name')
        return Response(CategorySerializer(cats, many=True).data)

    def post(self, request):
        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'name': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)

        slug = request.data.get('slug') or _slugify(name)
        description = request.data.get('description', '')

        if Category.objects.filter(slug=slug).exists():
            return Response({'slug': ['A category with this slug already exists.']}, status=status.HTTP_400_BAD_REQUEST)

        cat = CategoryRepository.create(
            name=name,
            slug=slug,
            description=description,
            parent=None,
            is_active=True,
            show_in_customer_ui=False,  # admin must approve vendor-created categories
        )
        return Response(CategorySerializer(cat).data, status=status.HTTP_201_CREATED)


class VendorSubcategoryCreateView(APIView):
    """
    POST /api/vendors/categories/<uuid:pk>/subcategories/
    Create a subcategory under the given parent category.
    """
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request, pk):
        parent = CategoryRepository.get_by_id(pk)
        if not parent:
            return Response({'error': 'Parent category not found.'}, status=status.HTTP_404_NOT_FOUND)

        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'name': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)

        slug = request.data.get('slug') or _slugify(name)
        description = request.data.get('description', '')

        if Category.objects.filter(slug=slug).exists():
            return Response({'slug': ['A category with this slug already exists.']}, status=status.HTTP_400_BAD_REQUEST)

        cat = CategoryRepository.create(
            name=name,
            slug=slug,
            description=description,
            parent=parent,
            is_active=True,
            show_in_customer_ui=False,
        )
        return Response(CategorySerializer(cat).data, status=status.HTTP_201_CREATED)
