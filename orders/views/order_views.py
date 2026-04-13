import base64
from io import BytesIO

import qrcode
import qrcode.constants
from django.db.models import Avg
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.actions.ordering import CreateOrdersFromCartAction, CancelOrderAction
from orders.data.order_repo import OrderRepository
from orders.models import Order, OrderRating
from orders.serializers import (
    CreateOrderSerializer, OrderSerializer, OrderTrackingSerializer, OrderRatingSerializer,
)


class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            action = CreateOrdersFromCartAction()
            created_orders = action.execute(
                user=request.user,
                delivery_address_id=serializer.validated_data["delivery_address_id"],
                payment_method=serializer.validated_data.get("payment_method", "cod"),
                notes=serializer.validated_data.get("notes", ""),
                coupon_code=serializer.validated_data.get("coupon_code", "").strip().upper(),
            )
            return Response(OrderSerializer(created_orders, many=True).data, status=status.HTTP_201_CREATED)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


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
        upi_string = f"upi://pay?pa=nexconnect@ybl&pn=NexConnect&am={amount}&cu=INR&tn=Order%20{order.order_number}"

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
