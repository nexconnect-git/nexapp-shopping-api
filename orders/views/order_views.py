import base64
from decimal import Decimal
from io import BytesIO

import qrcode
import qrcode.constants
from django.db.models import Avg
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Address
from backend.utils import haversine
from orders.actions.ordering import CreateOrdersFromCartAction, CancelOrderAction
from orders.data.cart_repo import CartRepository
from orders.data.order_repo import OrderRepository
from orders.models import Cart, Order, OrderRating
from orders.serializers import (
    CreateOrderSerializer, OrderSerializer, OrderTrackingSerializer, OrderRatingSerializer,
)


class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        try:
            action = CreateOrdersFromCartAction()
            created_orders = action.execute(
                user=request.user,
                delivery_address_id=vd["delivery_address_id"],
                payment_method=vd.get("payment_method", "cod"),
                notes=vd.get("notes", ""),
                coupon_code=vd.get("coupon_code", "").strip().upper(),
                wallet_amount=vd.get("wallet_amount", Decimal("0")),
                loyalty_points=vd.get("loyalty_points", 0),
                scheduled_for=vd.get("scheduled_for"),
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # If Razorpay payment proof was provided (new initiate-first flow),
        # verify the signature and mark all created orders as paid.
        rz_order_id = vd.get("razorpay_order_id", "").strip()
        rz_payment_id = vd.get("razorpay_payment_id", "").strip()
        rz_signature = vd.get("razorpay_signature", "").strip()

        if rz_order_id and rz_payment_id and rz_signature:
            from orders.services.razorpay_service import RazorpayService
            valid = RazorpayService().verify_payment_signature(
                razorpay_order_id=rz_order_id,
                razorpay_payment_id=rz_payment_id,
                razorpay_signature=rz_signature,
            )
            if valid:
                Order.objects.filter(pk__in=[o.pk for o in created_orders]).update(
                    razorpay_order_id=rz_order_id,
                    razorpay_payment_id=rz_payment_id,
                    is_payment_verified=True,
                )
                for o in created_orders:
                    o.is_payment_verified = True
            else:
                import logging as _log
                _log.getLogger(__name__).warning(
                    "Invalid Razorpay signature on order creation for user %s", request.user.id
                )

        return Response(OrderSerializer(created_orders, many=True).data, status=status.HTTP_201_CREATED)


class OrderListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return OrderRepository.get_customer_orders(
            self.request.user,
            self.request.query_params.get("status"),
        )


class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).prefetch_related("items", "tracking")


class CancelOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            action = CancelOrderAction()
            order = action.execute(str(pk), request.user)
            return Response(OrderSerializer(order).data)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class OrderTrackingView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderTrackingSerializer

    def get_queryset(self):
        return OrderRepository.get_tracking(self.kwargs["pk"], self.request.user)


class OrderPaymentQRView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            order = OrderRepository.get_by_id(pk)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        if order.delivery_partner != request.user and order.customer != request.user:
            return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        amount = str(order.total)
        
        from orders.models.setting import PlatformSetting
        setting = PlatformSetting.get_setting()
        upi_string = f"upi://pay?pa={setting.upi_id}&pn=NexConnect&am={amount}&cu=INR&tn=Order%20{order.order_number}"

        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(upi_string)
        qr.make(fit=True)
        qr_image = qr.make_image(fill_color="black", back_color="white")

        qr_buffer = BytesIO()
        qr_image.save(qr_buffer, format="PNG")
        qr_base64_string = base64.b64encode(qr_buffer.getvalue()).decode("utf-8")

        return Response({
            "order_number": order.order_number,
            "amount": amount,
            "qr_base64": f"data:image/png;base64,{qr_base64_string}",
            "upi_string": upi_string,
        })


class SubmitOrderRatingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.get(id=pk, customer=request.user)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        if order.status != "delivered":
            return Response({"error": "You can only rate delivered orders."}, status=status.HTTP_400_BAD_REQUEST)
        if hasattr(order, "rating"):
            return Response({"error": "You have already rated this order."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OrderRatingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        rating = OrderRating.objects.create(
            order=order, customer=request.user,
            delivery_partner=order.delivery_partner,
            rating=serializer.validated_data["rating"],
        )

        if order.delivery_partner:
            try:
                delivery_partner_profile = order.delivery_partner.delivery_profile
                avg = OrderRating.objects.filter(
                    delivery_partner=order.delivery_partner
                ).aggregate(avg=Avg("rating"))["avg"]
                delivery_partner_profile.average_rating = avg or rating.rating
                delivery_partner_profile.save(update_fields=["average_rating"])
            except Exception:
                pass

        return Response({"id": str(rating.id), "rating": rating.rating}, status=status.HTTP_201_CREATED)


class TipDeliveryPartnerView(APIView):
    """POST /api/orders/<pk>/tip/ — add a tip to a delivered order."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.get(id=pk, customer=request.user)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        if order.status != "delivered":
            return Response({"error": "You can only tip on delivered orders."}, status=status.HTTP_400_BAD_REQUEST)

        if not order.delivery_partner:
            return Response({"error": "No delivery partner assigned."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(str(request.data.get("amount", 0)))
        except Exception:
            return Response({"error": "Invalid tip amount."}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({"error": "Tip amount must be positive."}, status=status.HTTP_400_BAD_REQUEST)

        order.delivery_tip = amount
        order.save(update_fields=["delivery_tip", "updated_at"])
        return Response({"delivery_tip": str(order.delivery_tip)})


class CancellationPolicyView(APIView):
    """GET /api/orders/cancellation-policy/

    Returns the platform cancellation policy (no auth required).
    Frontend uses this to decide whether to show/disable the cancel button.
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        from orders.models.setting import PlatformSetting
        setting = PlatformSetting.get_setting()
        return Response({
            'window_minutes': setting.cancellation_window_minutes,
            'allowed_statuses': ['placed', 'confirmed', 'preparing', 'ready'],
        })


class DeliveryFeePreviewView(APIView):
    """GET /api/orders/delivery-fee-preview/?address_id=<uuid>

    Returns the estimated delivery fee for each vendor currently in the user's cart,
    based on the selected delivery address and the platform rate card.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        address_id = request.query_params.get("address_id")
        if not address_id:
            return Response({"error": "address_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            delivery_address = Address.objects.get(pk=address_id, user=request.user)
        except Address.DoesNotExist:
            return Response({"error": "Address not found."}, status=status.HTTP_404_NOT_FOUND)

        from orders.models import Cart
        from orders.models.setting import PlatformSetting

        try:
            cart = Cart.objects.prefetch_related("items__product__vendor").get(user=request.user)
        except Cart.DoesNotExist:
            return Response({"fees": [], "total_delivery_fee": "0.00"})

        platform = PlatformSetting.get_setting()
        vendor_seen: dict = {}
        fees = []

        for item in cart.items.select_related("product__vendor").all():
            vendor = item.product.vendor
            if vendor.id in vendor_seen:
                continue
            vendor_seen[vendor.id] = True

            distance = 0.0
            if delivery_address.latitude and delivery_address.longitude:
                distance = haversine(
                    float(vendor.latitude), float(vendor.longitude),
                    float(delivery_address.latitude), float(delivery_address.longitude),
                )

            subtotal = sum(
                ci.product.price * ci.quantity
                for ci in cart.items.all()
                if ci.product.vendor_id == vendor.id
            )

            if platform.free_delivery_above > 0 and subtotal >= platform.free_delivery_above:
                fee = Decimal("0")
                reason = f"Free delivery on orders above ₹{platform.free_delivery_above}"
            else:
                fee = (
                    platform.delivery_base_fee
                    + platform.delivery_per_km_fee * Decimal(str(round(distance, 2)))
                )
                reason = f"₹{platform.delivery_base_fee} base + ₹{platform.delivery_per_km_fee}/km × {round(distance, 1)} km"

            fees.append({
                "vendor_id": str(vendor.id),
                "vendor_name": vendor.store_name,
                "distance_km": round(distance, 2),
                "delivery_fee": str(fee.quantize(Decimal("0.01"))),
                "reason": reason,
            })

        total = sum(Decimal(f["delivery_fee"]) for f in fees)
        return Response({"fees": fees, "total_delivery_fee": str(total.quantize(Decimal("0.01")))})


class ReorderView(APIView):
    """POST /api/orders/<pk>/reorder/

    Clears the current cart and re-adds all available items from a previous order.
    Returns the updated cart so the frontend can navigate straight to checkout.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.prefetch_related("items__product").get(
                pk=pk, customer=request.user
            )
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

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
                existing.save(update_fields=["quantity"])
            else:
                cart.items.create(product=product, quantity=item.quantity)

        from orders.serializers import CartSerializer
        data = CartSerializer(cart).data
        if skipped:
            data["skipped"] = skipped
        return Response(data, status=status.HTTP_200_OK)
