from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.data.cart_repo import CartRepository
from orders.models import Order
from orders.serializers import CartSerializer


class ReorderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.prefetch_related('items__product').get(pk=pk, customer=request.user)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        cart, _ = CartRepository.get_or_create_cart(request.user)
        cart.items.all().delete()

        skipped = []
        for item in order.items.all():
            product = item.product
            if product is None or not product.is_available or product.stock <= 0:
                skipped.append(item.product_name)
                continue
            existing = cart.items.filter(product=product).first()
            if existing:
                existing.quantity += item.quantity
                existing.save(update_fields=['quantity'])
            else:
                cart.items.create(product=product, quantity=item.quantity)

        data = CartSerializer(cart).data
        if skipped:
            data['skipped'] = skipped
        return Response(data, status=status.HTTP_200_OK)
