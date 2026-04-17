"""Wishlist views — GET list, POST add, DELETE remove, GET check."""

from django.db import IntegrityError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from products.models import Product, Wishlist
from products.serializers import ProductSerializer


class WishlistView(APIView):
    """GET /api/products/wishlist/ — list all wishlisted products."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = Wishlist.objects.filter(user=request.user).select_related('product')
        products = [item.product for item in items]
        data = ProductSerializer(products, many=True, context={'request': request}).data
        return Response({'count': len(data), 'results': data})


class WishlistToggleView(APIView):
    """POST /api/products/wishlist/<pk>/toggle/ — add or remove a product."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        item = Wishlist.objects.filter(user=request.user, product=product).first()
        if item:
            item.delete()
            return Response({'wishlisted': False})
        else:
            try:
                Wishlist.objects.create(user=request.user, product=product)
            except IntegrityError:
                pass
            return Response({'wishlisted': True}, status=status.HTTP_201_CREATED)


class WishlistStatusView(APIView):
    """GET /api/products/wishlist/status/?ids=uuid1,uuid2 — bulk check status."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        ids_param = request.query_params.get('ids', '')
        if not ids_param:
            return Response({})
        ids = [i.strip() for i in ids_param.split(',') if i.strip()]
        wishlisted = set(
            str(pk)
            for pk in Wishlist.objects.filter(
                user=request.user, product_id__in=ids
            ).values_list('product_id', flat=True)
        )
        return Response({pid: pid in wishlisted for pid in ids})
