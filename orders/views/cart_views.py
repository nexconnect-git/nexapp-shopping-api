from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.actions.audit_actions import CreateAdminAuditLogAction
from orders.data.cart_repo import CartRepository
from orders.serializers import (
    AddToCartSerializer,
    CartFulfillmentEventSerializer,
    CartItemSerializer,
    CartSerializer,
    RefreshCartFulfillmentSerializer,
    ReplaceCartSerializer,
)
from products.data.product_repository import ProductRepository
from products.models import Product
from vendors.models import FulfillmentNode, FulfillmentNodeInventory


def _fulfillment_payload(serializer):
    return {
        "node_id": serializer.validated_data.get("fulfillment_node_id"),
        "promise_id": serializer.validated_data.get("fulfillment_promise_id", ""),
        "promise_expires_at": serializer.validated_data.get("fulfillment_promise_expires_at"),
    }


def _resolve_fulfillment_node(product, payload):
    node_id = payload.get("node_id")
    if not node_id:
        return None, None
    try:
        node = FulfillmentNode.objects.select_related("vendor").get(pk=node_id)
    except FulfillmentNode.DoesNotExist:
        return None, Response(
            {
                "error": (
                    "Delivery is no longer available for your selected location. "
                    "Please refresh availability or choose your location again."
                ),
                "code": "invalid_fulfillment_node",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if node.status != "active" or not node.is_accepting_orders:
        return None, Response(
            {
                "error": (
                    "This store is not accepting delivery orders for your selected location right now. "
                    "Please try another store or update your location."
                ),
                "code": "fulfillment_node_unavailable",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if node.vendor_id and str(node.vendor_id) != str(product.vendor_id):
        return None, Response(
            {
                "error": "This item is not available for delivery from your selected location.",
                "code": "fulfillment_node_product_mismatch",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    return node, None


def _validate_fulfillment_payload(payload):
    expires_at = payload.get("promise_expires_at")
    if expires_at and expires_at <= timezone.now():
        return Response(
            {
                "error": "Delivery promise expired. Refresh availability before updating your cart.",
                "code": "fulfillment_promise_expired",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    return None


def _validate_node_inventory(node, product, requested_quantity):
    if not node:
        return None
    inventory = FulfillmentNodeInventory.objects.filter(node=node, product=product).first()
    if not inventory:
        return None
    if not inventory.is_available or inventory.sellable_stock < requested_quantity:
        return Response(
            {
                "error": (
                    f"'{product.name}' only has {inventory.sellable_stock} unit(s) "
                    "available from the selected fulfillment node."
                ),
                "code": "fulfillment_node_stock_unavailable",
                "available": inventory.sellable_stock,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    return None


def _cart_fulfillment_conflict_response(cart, node, product):
    if not cart.fulfillment_node_id or not node:
        return None
    if str(cart.fulfillment_node_id) == str(node.id):
        return None
    return Response(
        {
            "error": "Your basket is locked to another fulfillment promise. Replace basket?",
            "code": "cart_fulfillment_conflict",
            "existing_fulfillment_node_id": str(cart.fulfillment_node_id),
            "existing_fulfillment_node_name": cart.fulfillment_node.name if cart.fulfillment_node else "",
            "incoming_fulfillment_node_id": str(node.id),
            "incoming_fulfillment_node_name": node.name,
            "incoming_store_id": str(product.vendor_id),
            "incoming_store_name": product.vendor.store_name,
        },
        status=status.HTTP_409_CONFLICT,
    )


def _lock_cart_fulfillment(cart, node, payload):
    if not node:
        return
    cart.fulfillment_node = node
    cart.fulfillment_promise_id = payload.get("promise_id") or ""
    cart.fulfillment_promise_expires_at = payload.get("promise_expires_at")
    cart.fulfillment_locked_at = timezone.now()
    cart.save(update_fields=[
        "fulfillment_node",
        "fulfillment_promise_id",
        "fulfillment_promise_expires_at",
        "fulfillment_locked_at",
        "updated_at",
    ])


def _cart_audit_metadata(cart, metadata):
    safe_metadata = metadata if isinstance(metadata, dict) else {}
    return {
        **safe_metadata,
        "cart_id": str(cart.id),
        "cart_fulfillment_node_id": str(cart.fulfillment_node_id or ""),
        "cart_fulfillment_node_name": cart.fulfillment_node.name if cart.fulfillment_node else "",
        "cart_item_count": cart.total_items,
    }


def _clear_cart_fulfillment_if_empty(cart):
    if cart.items.exists():
        return
    cart.fulfillment_node = None
    cart.fulfillment_promise_id = ""
    cart.fulfillment_promise_expires_at = None
    cart.fulfillment_locked_at = None
    cart.save(update_fields=[
        "fulfillment_node",
        "fulfillment_promise_id",
        "fulfillment_promise_expires_at",
        "fulfillment_locked_at",
        "updated_at",
    ])


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
        fulfillment = _fulfillment_payload(serializer)
        fulfillment_error = _validate_fulfillment_payload(fulfillment)
        if fulfillment_error:
            return fulfillment_error

        try:
            product = Product.objects.get(
                pk=product_id,
                **ProductRepository.customer_visible_filter(),
            )
        except Product.DoesNotExist:
            return Response({"error": "Product not found or unavailable."}, status=status.HTTP_404_NOT_FOUND)

        cart, _ = CartRepository.get_or_create_cart(request.user)
        node, node_error = _resolve_fulfillment_node(product, fulfillment)
        if node_error:
            return node_error

        # Enforce single-vendor cart
        existing_items = cart.items.select_related("product__vendor").all()
        conflict_response = _cart_fulfillment_conflict_response(cart, node, product)
        if conflict_response:
            return conflict_response
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
        stock_error = _validate_node_inventory(node, product, existing_quantity + quantity)
        if stock_error:
            return stock_error

        _, created = CartRepository.add_item(cart, product, quantity)
        _lock_cart_fulfillment(cart, node, fulfillment)

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
        fulfillment = _fulfillment_payload(serializer)
        fulfillment_error = _validate_fulfillment_payload(fulfillment)
        if fulfillment_error:
            return fulfillment_error

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
        node, node_error = _resolve_fulfillment_node(product, fulfillment)
        if node_error:
            return node_error
        stock_error = _validate_node_inventory(node, product, quantity)
        if stock_error:
            return stock_error
        cart.items.select_for_update().all().delete()
        if not node:
            _clear_cart_fulfillment_if_empty(cart)
        CartRepository.add_item(cart, product, quantity)
        _lock_cart_fulfillment(cart, node, fulfillment)
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
                cart = cart_item.cart
                cart_item.delete()
                _clear_cart_fulfillment_if_empty(cart)
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
            stock_error = _validate_node_inventory(
                cart_item.cart.fulfillment_node,
                cart_item.product,
                quantity,
            )
            if stock_error:
                return stock_error
            cart_item.quantity = quantity
            cart_item.save(update_fields=["quantity"])

        return Response(CartItemSerializer(cart_item).data)

    def delete(self, request, pk):
        try:
            cart_item = CartRepository.get_cart_item(pk, request.user)
        except Exception:
            return Response({"error": "Cart item not found."}, status=status.HTTP_404_NOT_FOUND)
        cart_item.delete()
        _clear_cart_fulfillment_if_empty(cart_item.cart)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClearCartView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        CartRepository.clear_cart(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RefreshCartFulfillmentView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = RefreshCartFulfillmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fulfillment = _fulfillment_payload(serializer)
        fulfillment_error = _validate_fulfillment_payload(fulfillment)
        if fulfillment_error:
            return fulfillment_error

        cart, _ = CartRepository.get_or_create_cart(request.user)
        cart_items = list(
            cart.items.select_for_update().select_related("product__vendor")
        )
        if not cart_items:
            _clear_cart_fulfillment_if_empty(cart)
            return Response(CartSerializer(cart).data)

        first_product = cart_items[0].product
        node, node_error = _resolve_fulfillment_node(first_product, fulfillment)
        if node_error:
            return node_error

        if cart.fulfillment_node_id and str(cart.fulfillment_node_id) != str(node.id):
            return Response(
                {
                    "error": "Cart belongs to another fulfillment promise.",
                    "code": "cart_fulfillment_conflict",
                    "existing_fulfillment_node_id": str(cart.fulfillment_node_id),
                    "existing_fulfillment_node_name": cart.fulfillment_node.name if cart.fulfillment_node else "",
                    "incoming_fulfillment_node_id": str(node.id),
                    "incoming_fulfillment_node_name": node.name,
                },
                status=status.HTTP_409_CONFLICT,
            )

        for item in cart_items:
            if node.vendor_id and str(node.vendor_id) != str(item.product.vendor_id):
                return Response(
                    {
                        "error": "Cart contains items outside the selected fulfillment node.",
                        "code": "cart_fulfillment_node_mismatch",
                        "fulfillment_node_id": str(node.id),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            stock_error = _validate_node_inventory(node, item.product, item.quantity)
            if stock_error:
                return stock_error

        _lock_cart_fulfillment(cart, node, fulfillment)
        return Response(CartSerializer(cart).data)


class CartFulfillmentEventView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CartFulfillmentEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart, _ = CartRepository.get_or_create_cart(request.user)
        event_type = serializer.validated_data["event_type"]
        metadata = _cart_audit_metadata(cart, serializer.validated_data.get("metadata"))
        CreateAdminAuditLogAction().execute(
            request=request,
            actor=request.user,
            action="other",
            entity_type="customer_cart",
            entity_id=str(cart.id),
            summary=f"Customer cart fulfillment event: {event_type}",
            metadata={
                "event_type": event_type,
                **metadata,
            },
        )
        return Response({"status": "recorded"}, status=status.HTTP_201_CREATED)
