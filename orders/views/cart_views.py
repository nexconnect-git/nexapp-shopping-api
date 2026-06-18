from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.data.cart_repo import CartRepository
from orders.serializers import AddToCartSerializer, CartSerializer, CartItemSerializer, ReplaceCartSerializer
from products.data.product_repository import ProductRepository
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
            product = Product.objects.get(
                pk=product_id,
                **ProductRepository.customer_visible_filter(),
            )
        except Product.DoesNotExist:
            return Response({"error": "Product not found or unavailable."}, status=status.HTTP_404_NOT_FOUND)

        cart, _ = CartRepository.get_or_create_cart(request.user)

        # Enforce single-vendor cart
        existing_items = cart.items.select_related("product__vendor").all()
        if existing_items.exists():
            existing_item = existing_items.first()
            existing_vendor_id = str(existing_item.product.vendor_id)
            if existing_vendor_id != str(product.vendor_id):
                return Response(
                    {
                        "error": f"Your basket has items from {existing_item.product.vendor.store_name}. To order from {product.vendor.store_name}, replace basket?",
                        "code": "cart_store_conflict",
                        "existing_store_id": existing_vendor_id,
                        "existing_store_name": existing_item.product.vendor.store_name,
                        "incoming_store_id": str(product.vendor_id),
                        "incoming_store_name": product.vendor.store_name,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        existing_quantity = next(
            (
                item.quantity
                for item in existing_items
                if str(item.product_id) == str(product.id)
            ),
            0,
        )
        if existing_quantity + quantity > product.stock:
            return Response(
                {
                    "error": (
                        f"'{product.name}' only has {product.stock} unit(s) in stock "
                        f"but {existing_quantity + quantity} requested."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        _, created = CartRepository.add_item(cart, product, quantity)

        return Response(
            CartSerializer(cart).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ReplaceCartView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = ReplaceCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data["product_id"]
        quantity = serializer.validated_data.get("quantity", 1)

        try:
            product = (
                Product.objects.select_for_update(of=("self",))
                .select_related("vendor", "catalog_product")
                .get(
                    pk=product_id,
                    **ProductRepository.customer_visible_filter(),
                )
            )
        except Product.DoesNotExist:
            return Response({"error": "Product not found or unavailable."}, status=status.HTTP_404_NOT_FOUND)

        if quantity > product.stock:
            return Response(
                {
                    "error": (
                        f"'{product.name}' only has {product.stock} unit(s) in stock "
                        f"but {quantity} requested."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart, _ = CartRepository.get_or_create_cart(request.user)
        cart.items.select_for_update().all().delete()
        CartRepository.add_item(cart, product, quantity)
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


class UpdateCartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            cart_item = CartRepository.get_cart_item(pk, request.user)
        except Exception:
            return Response({"error": "Cart item not found."}, status=status.HTTP_404_NOT_FOUND)

        quantity = request.data.get("quantity")
        if quantity is not None:
            quantity = int(quantity)
            if quantity <= 0:
                cart_item.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            if quantity > cart_item.product.stock:
                return Response(
                    {
                        "error": (
                            f"'{cart_item.product.name}' only has {cart_item.product.stock} unit(s) in stock "
                            f"but {quantity} requested."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            cart_item.quantity = quantity
            cart_item.save(update_fields=["quantity"])

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
