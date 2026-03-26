import math
from collections import defaultdict
from decimal import Decimal

from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from accounts.permissions import IsAdminRole

from .models import Cart, CartItem, Order, OrderItem, OrderTracking
from .serializers import (
    CartSerializer,
    CartItemSerializer,
    AddToCartSerializer,
    OrderSerializer,
    CreateOrderSerializer,
    OrderTrackingSerializer,
)
from products.models import Product
from accounts.models import Address
from notifications.models import Notification


def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return R * c


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)


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
            return Response(
                {"error": "Product not found or unavailable."},
                status=status.HTTP_404_NOT_FOUND,
            )

        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={"quantity": quantity},
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()

        return Response(
            CartSerializer(cart).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class UpdateCartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            cart_item = CartItem.objects.get(pk=pk, cart__user=request.user)
        except CartItem.DoesNotExist:
            return Response(
                {"error": "Cart item not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

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
            cart_item = CartItem.objects.get(pk=pk, cart__user=request.user)
        except CartItem.DoesNotExist:
            return Response(
                {"error": "Cart item not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClearCartView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        try:
            cart = Cart.objects.get(user=request.user)
            cart.items.all().delete()
        except Cart.DoesNotExist:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        delivery_address_id = serializer.validated_data["delivery_address_id"]
        notes = serializer.validated_data.get("notes", "")
        payment_method = serializer.validated_data.get("payment_method", "cod")

        try:
            delivery_address = Address.objects.get(
                pk=delivery_address_id, user=request.user
            )
        except Address.DoesNotExist:
            return Response(
                {"error": "Delivery address not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            cart = Cart.objects.prefetch_related("items__product__vendor").get(
                user=request.user
            )
        except Cart.DoesNotExist:
            return Response(
                {"error": "Cart is empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart_items = cart.items.select_related("product__vendor").all()
        if not cart_items.exists():
            return Response(
                {"error": "Cart is empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Group cart items by vendor
        vendor_items = defaultdict(list)
        for item in cart_items:
            vendor_items[item.product.vendor].append(item)

        created_orders = []

        for vendor, items in vendor_items.items():
            subtotal = sum(item.product.price * item.quantity for item in items)

            # Calculate delivery fee: flat 30 + 5 per km
            distance = 0
            if delivery_address.latitude and delivery_address.longitude:
                distance = haversine(
                    float(vendor.latitude),
                    float(vendor.longitude),
                    float(delivery_address.latitude),
                    float(delivery_address.longitude),
                )
            delivery_fee = Decimal("30") + Decimal("5") * Decimal(str(round(distance, 2)))
            total = subtotal + delivery_fee

            order = Order.objects.create(
                customer=request.user,
                vendor=vendor,
                delivery_address=delivery_address,
                payment_method=payment_method,
                subtotal=subtotal,
                delivery_fee=delivery_fee,
                total=total,
                notes=notes,
                delivery_latitude=delivery_address.latitude,
                delivery_longitude=delivery_address.longitude,
            )

            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    product_name=item.product.name,
                    product_price=item.product.price,
                    quantity=item.quantity,
                    subtotal=item.product.price * item.quantity,
                )

            OrderTracking.objects.create(
                order=order,
                status="placed",
                description="Order has been placed.",
            )

            # Notify vendor of new order
            Notification.objects.create(
                user=vendor.user,
                title="New Order Received",
                message=f"You have a new order #{order.order_number} worth ${order.total}.",
                notification_type="order",
                data={"order_id": str(order.id), "order_number": order.order_number},
            )

            created_orders.append(order)

        # Clear cart
        cart.items.all().delete()

        return Response(
            OrderSerializer(created_orders, many=True).data,
            status=status.HTTP_201_CREATED,
        )


class OrderListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        qs = Order.objects.filter(customer=self.request.user)
        order_status = self.request.query_params.get("status")
        if order_status:
            qs = qs.filter(status=order_status)
        return qs


class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).prefetch_related(
            "items", "tracking"
        )


class CancelOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk, customer=request.user)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if order.status not in ("placed", "confirmed"):
            return Response(
                {"error": "Order can only be cancelled if placed or confirmed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = "cancelled"
        order.save(update_fields=["status", "updated_at"])

        OrderTracking.objects.create(
            order=order,
            status="cancelled",
            description="Order cancelled by customer.",
        )

        # Notify vendor of cancellation
        Notification.objects.create(
            user=order.vendor.user,
            title="Order Cancelled",
            message=f"Order #{order.order_number} has been cancelled by the customer.",
            notification_type="order",
            data={"order_id": str(order.id), "order_number": order.order_number},
        )

        return Response(OrderSerializer(order).data)


class OrderTrackingView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderTrackingSerializer

    def get_queryset(self):
        return OrderTracking.objects.filter(
            order_id=self.kwargs["pk"],
            order__customer=self.request.user,
        )


# ── Admin views ──────────────────────────────────────────────────────────────

class AdminOrderPagination(PageNumberPagination):
    page_size = 20


class AdminOrderListView(generics.ListAPIView):
    """GET /api/admin/orders/ — list all orders."""
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = OrderSerializer

    def get_queryset(self):
        qs = Order.objects.select_related('customer', 'vendor').order_by('-placed_at')
        order_status = self.request.query_params.get('status')
        if order_status:
            qs = qs.filter(status=order_status)
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(order_number__icontains=search)
        vendor = self.request.query_params.get('vendor')
        if vendor:
            qs = qs.filter(vendor_id=vendor)
        customer = self.request.query_params.get('customer')
        if customer:
            qs = qs.filter(customer_id=customer)
        partner = self.request.query_params.get('delivery_partner')
        if partner:
            qs = qs.filter(delivery_partner_id=partner)
        return qs

    def get(self, request, *args, **kwargs):
        qs = self.get_queryset()
        paginator = AdminOrderPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(OrderSerializer(page, many=True).data)


class AdminOrderDetailView(APIView):
    """GET/PATCH /api/admin/orders/<pk>/ — view or update an order."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get(self, pk):
        try:
            return Order.objects.prefetch_related('items', 'tracking').get(pk=pk)
        except Order.DoesNotExist:
            return None

    def get(self, request, pk):
        order = self._get(pk)
        if not order:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrderSerializer(order).data)

    def patch(self, request, pk):
        order = self._get(pk)
        if not order:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)
        new_status = request.data.get('status')
        valid = ['placed', 'confirmed', 'preparing', 'ready', 'picked_up', 'on_the_way', 'delivered', 'cancelled']
        if new_status and new_status not in valid:
            return Response({'error': f'Invalid status.'}, status=status.HTTP_400_BAD_REQUEST)
        if new_status:
            order.status = new_status
            order.save(update_fields=['status', 'updated_at'])
            OrderTracking.objects.create(order=order, status=new_status, description=f'Status updated by admin to {new_status}.')
        return Response(OrderSerializer(order).data)
