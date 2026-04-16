from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.data.cart_repo import CartRepository
from orders.serializers import AddToCartSerializer, CartSerializer, CartItemSerializer
from products.models import Product


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart, _ = CartRepository.get_or_create_cart(request.user)
        return Response(CartSerializer(cart).data)


class AddToCartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data["product_id"]
        quantity = serializer.validated_data.get("quantity", 1)

        try:
            product = Product.objects.get(pk=product_id, is_available=True)
        except Product.DoesNotExist:
            return Response({"error": "Product not found or unavailable."}, status=status.HTTP_404_NOT_FOUND)

        cart, _ = CartRepository.get_or_create_cart(request.user)

        # Enforce single-vendor cart
        existing_items = cart.items.select_related("product__vendor").all()
        if existing_items.exists():
            existing_vendor_id = str(existing_items.first().product.vendor_id)
            if existing_vendor_id != str(product.vendor_id):
                return Response(
                    {"error": "Your cart contains items from a different vendor. Clear your cart first."},
                    status=status.HTTP_409_CONFLICT,
                )

        _, created = CartRepository.add_item(cart, product, quantity)

        return Response(
            CartSerializer(cart).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class UpdateCartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            cart_item = CartRepository.get_cart_item(pk, request.user)
        except Exception:
            return Response({"error": "Cart item not found."}, status=status.HTTP_404_NOT_FOUND)

        quantity = request.data.get("quantity")
        if quantity is not None:
            if int(quantity) <= 0:
                cart_item.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            cart_item.quantity = int(quantity)
            cart_item.save()

        return Response(CartItemSerializer(cart_item).data)

    def delete(self, request, pk):
        try:
            cart_item = CartRepository.get_cart_item(pk, request.user)
        except Exception:
            return Response({"error": "Cart item not found."}, status=status.HTTP_404_NOT_FOUND)
        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClearCartView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        CartRepository.clear_cart(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
