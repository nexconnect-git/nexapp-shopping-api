from decimal import Decimal

from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.data.coupon_repo import CouponRepository
from orders.models import Coupon, CouponUsage
from orders.serializers import CouponSerializer


class ValidateCouponView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get("code", "").strip().upper()
        cart_total = request.data.get("cart_total", 0)

        if not code:
            return Response({"error": "Coupon code is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            coupon = CouponRepository.get_active_coupon(code)
        except Coupon.DoesNotExist:
            return Response({"valid": False, "error": "Invalid coupon code."}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        if coupon.valid_from > now:
            return Response({"valid": False, "error": "Coupon is not yet valid."}, status=status.HTTP_400_BAD_REQUEST)
        if coupon.valid_until and coupon.valid_until < now:
            return Response({"valid": False, "error": "Coupon has expired."}, status=status.HTTP_400_BAD_REQUEST)
        if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
            return Response({"valid": False, "error": "Coupon usage limit reached."}, status=status.HTTP_400_BAD_REQUEST)

        user_uses = CouponRepository.get_user_usage_count(coupon, request.user)
        if user_uses >= coupon.per_user_limit:
            return Response({"valid": False, "error": "You have already used this coupon."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            total = Decimal(str(cart_total))
        except Exception:
            total = Decimal("0")

        if total < coupon.min_order_amount:
            return Response(
                {"valid": False, "error": f"Minimum order amount is ₦{coupon.min_order_amount}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        discount = coupon.calculate_discount(total)
        return Response({
            "valid": True, "code": coupon.code, "title": coupon.title,
            "discount_type": coupon.discount_type, "discount": str(discount),
            "message": f'"{coupon.title}" applied! You save ₦{discount}.',
        })


class CustomerCouponListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CouponSerializer

    def get_queryset(self):
        return CouponRepository.get_valid_customer_coupons()


class AdminCouponViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = CouponSerializer

    def get_queryset(self):
        if self.request.user.role != "admin":
            return Coupon.objects.none()
        return CouponRepository.get_all_admin()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
