import base64
from decimal import Decimal
from io import BytesIO

import qrcode
import qrcode.constants
from django.db import transaction
from django.db.models import Avg
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Address
from helpers.delivery_quotes import DeliveryServiceabilityError, FarDeliveryConfirmationRequired, quote_vendor_delivery
from orders.actions.checkout import available_slots_for_cart, calculate_checkout_preview, public_price_breakup
from orders.actions.ordering import CreateOrdersFromCartAction, CancelOrderAction
from orders.data.cart_repo import CartRepository
from orders.data.order_repo import OrderRepository
from orders.models import Cart, Order, OrderRating, PlatformSetting
from orders.serializers import (
    CreateOrderSerializer, OrderSerializer, OrderTrackingSerializer, OrderRatingSerializer,
)


class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        rz_order_id = vd.get("razorpay_order_id", "").strip()
        rz_payment_id = vd.get("razorpay_payment_id", "").strip()
        rz_signature = vd.get("razorpay_signature", "").strip()
        has_razorpay_proof = bool(rz_order_id and rz_payment_id and rz_signature)
        payment_method = vd.get("payment_method", "cod")

        platform_setting = PlatformSetting.get_setting()
        if payment_method == "cod" and not platform_setting.is_cod_enabled():
            return Response(
                {"error": "Cash on delivery is currently disabled."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if payment_method == "razorpay" and not platform_setting.is_online_payment_enabled():
            return Response(
                {"error": "Online payment is currently disabled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if payment_method == "razorpay" and not has_razorpay_proof:
            return Response(
                {"error": "Online payment was not completed. Please finish payment before placing the order."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if has_razorpay_proof:
            from orders.services.razorpay_service import RazorpayService
            if not RazorpayService().verify_payment_signature(
                razorpay_order_id=rz_order_id,
                razorpay_payment_id=rz_payment_id,
                razorpay_signature=rz_signature,
            ):
                return Response(
                    {"error": "Payment verification failed. Please try payment again."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            with transaction.atomic():
                action = CreateOrdersFromCartAction()
                created_orders = action.execute(
                    user=request.user,
                    delivery_address_id=vd["delivery_address_id"],
                    payment_method=payment_method,
                    notes=vd.get("notes", ""),
                    coupon_code=vd.get("coupon_code", "").strip().upper(),
                    wallet_amount=vd.get("wallet_amount", Decimal("0")),
                    loyalty_points=vd.get("loyalty_points", 0),
                    scheduled_for=vd.get("scheduled_for"),
                    confirm_far_delivery=vd.get("confirm_far_delivery", False),
                    cod_upi_confirmed=vd.get("cod_upi_confirmed", False),
                    client_price_breakup=vd.get("client_price_breakup", {}),
                )

                if has_razorpay_proof:
                    Order.objects.filter(pk__in=[o.pk for o in created_orders]).update(
                        razorpay_order_id=rz_order_id,
                        razorpay_payment_id=rz_payment_id,
                        is_payment_verified=True,
                    )
                    for order in created_orders:
                        order.razorpay_order_id = rz_order_id
                        order.razorpay_payment_id = rz_payment_id
                        order.is_payment_verified = True
        except FarDeliveryConfirmationRequired as exc:
            return Response(
                {
                    "error": "Far delivery confirmation required.",
                    "code": "far_delivery_confirmation_required",
                    "quotes": exc.quotes,
                },
                status=status.HTTP_409_CONFLICT,
            )
        except DeliveryServiceabilityError as exc:
            return Response(
                {
                    "error": str(exc),
                    "code": "delivery_not_serviceable",
                    "details": exc.quote.as_dict(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as exc:
            payload = exc.args[0] if exc.args else str(exc)
            if isinstance(payload, dict):
                return Response(payload, status=status.HTTP_400_BAD_REQUEST)
            return Response({"error": str(payload)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(OrderSerializer(created_orders, many=True).data, status=status.HTTP_201_CREATED)


class OrderListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return OrderRepository.get_customer_orders(
            self.request.user,
            self.request.query_params.get("status"),
        )

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data = {
            "count": len(response.data) if isinstance(response.data, list) else response.data.get("count", 0),
            "results": response.data if isinstance(response.data, list) else response.data.get("results", response.data),
            "summary": OrderRepository.get_customer_order_summary(request.user),
        }
        return response


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
        far_delivery_quotes = []
        cart_items = list(cart.items.select_related("product__vendor").all())

        for item in cart_items:
            vendor = item.product.vendor
            if vendor.id in vendor_seen:
                continue
            vendor_seen[vendor.id] = True

            vendor_items = [ci for ci in cart_items if ci.product.vendor_id == vendor.id]
            subtotal = sum(ci.product.price * ci.quantity for ci in vendor_items)
            quote = quote_vendor_delivery(
                vendor=vendor,
                address=delivery_address,
                products=[ci.product for ci in vendor_items],
                quantities={str(ci.product.id): ci.quantity for ci in vendor_items},
                subtotal=subtotal,
                platform=platform,
            )
            payload = quote.as_dict()
            if platform.free_delivery_above > 0 and subtotal >= platform.free_delivery_above:
                payload["delivery_fee"] = "0.00"
                payload["reason"] = f"Free delivery on orders above ₹{platform.free_delivery_above}"
            else:
                payload["reason"] = f"Distance-based delivery for {round(payload['distance_km'], 1)} km"
            fees.append(payload)
            if quote.requires_far_delivery_confirmation:
                far_delivery_quotes.append(payload)

        total = sum((Decimal(f["delivery_fee"]) for f in fees), Decimal("0.00"))
        return Response(
            {
                "fees": fees,
                "total_delivery_fee": str(total.quantize(Decimal("0.01"))),
                "requires_far_delivery_confirmation": bool(far_delivery_quotes),
                "far_delivery_quotes": far_delivery_quotes,
            }
        )


class CheckoutPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            preview = calculate_checkout_preview(
                user=request.user,
                delivery_address_id=request.data.get("delivery_address_id"),
                payment_method=request.data.get("payment_method", "cod"),
                coupon_code=request.data.get("coupon_code", ""),
                wallet_amount=request.data.get("wallet_amount", Decimal("0")),
                scheduled_for=request.data.get("scheduled_for"),
                confirm_far_delivery=bool(request.data.get("confirm_far_delivery", False)),
                cod_upi_confirmed=bool(request.data.get("cod_upi_confirmed", False)),
                require_cod_confirmation=False,
            )
        except FarDeliveryConfirmationRequired as exc:
            return Response(
                {
                    "error": "Far delivery confirmation required.",
                    "code": "far_delivery_confirmation_required",
                    "quotes": exc.quotes,
                },
                status=status.HTTP_409_CONFLICT,
            )
        except DeliveryServiceabilityError as exc:
            return Response(
                {
                    "error": str(exc),
                    "code": "delivery_not_serviceable",
                    "details": exc.quote.as_dict(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as exc:
            payload = exc.args[0] if exc.args else str(exc)
            if isinstance(payload, dict):
                return Response(payload, status=status.HTTP_400_BAD_REQUEST)
            return Response({"error": str(payload)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "price_breakup": public_price_breakup(preview),
            "delivery_quotes": preview["delivery_quotes"],
            "requires_far_delivery_confirmation": preview["requires_far_delivery_confirmation"],
            "far_delivery_quotes": preview["far_delivery_quotes"],
            "cod_upi_confirmation_required": preview["cod_upi_confirmation_required"],
            "cod_upi_confirmed": preview["cod_upi_confirmed"],
            "cod_upi_message": preview["cod_upi_message"],
        })


class AvailableSlotsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            slots = available_slots_for_cart(
                request.user,
                start_date=request.query_params.get("date"),
                days=min(int(request.query_params.get("days", 7)), 14),
            )
        except ValueError as exc:
            payload = exc.args[0] if exc.args else str(exc)
            if isinstance(payload, dict):
                return Response(payload, status=status.HTTP_400_BAD_REQUEST)
            return Response({"error": str(payload)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"results": slots})


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
