from decimal import Decimal

from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Address
from helpers.cache_helpers import cached_api_response
from helpers.delivery_quotes import quote_vendor_delivery
from orders.data.coupon_repo import CouponRepository
from orders.models import Cart, Coupon, CouponUsage, PlatformSetting
from orders.serializers import CouponSerializer


def _cart_total_for_user(user) -> Decimal:
    try:
        cart = Cart.objects.get(user=user)
    except Cart.DoesNotExist:
        return Decimal("0")
    return Decimal(str(cart.total_amount))


def _delivery_fee_for_cart(user, address_id: str | None) -> Decimal:
    if not address_id:
        return Decimal("0")
    try:
        address = Address.objects.get(pk=address_id, user=user)
        cart = Cart.objects.prefetch_related("items__product__vendor").get(user=user)
    except (Address.DoesNotExist, Cart.DoesNotExist):
        return Decimal("0")

    platform = PlatformSetting.get_setting()
    cart_items = list(cart.items.select_related("product__vendor").all())
    vendor_ids = set()
    delivery_fee = Decimal("0")
    for item in cart_items:
        vendor = item.product.vendor
        if vendor.id in vendor_ids:
            continue
        vendor_ids.add(vendor.id)
        vendor_items = [ci for ci in cart_items if ci.product.vendor_id == vendor.id]
        subtotal = sum(ci.product.price * ci.quantity for ci in vendor_items)
        if platform.free_delivery_above > 0 and subtotal >= platform.free_delivery_above:
            continue
        quote = quote_vendor_delivery(
            vendor=vendor,
            address=address,
            products=[ci.product for ci in vendor_items],
            quantities={str(ci.product.id): ci.quantity for ci in vendor_items},
            subtotal=subtotal,
            platform=platform,
        )
        if quote.is_serviceable:
            delivery_fee += quote.delivery_fee
    return delivery_fee


class ValidateCouponView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get("code", "").strip().upper()
        cart_total = request.data.get("cart_total", 0)
        address_id = request.data.get("address_id")

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
            total = _cart_total_for_user(request.user)
        if total <= 0:
            total = _cart_total_for_user(request.user)

        if total < coupon.min_order_amount:
            return Response(
                {"valid": False, "error": f"Minimum order amount is Rs.{coupon.min_order_amount}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        delivery_discount = Decimal("0")
        if coupon.discount_type == "free_delivery":
            delivery_discount = _delivery_fee_for_cart(request.user, address_id)
        discount = (coupon.calculate_discount(total) + delivery_discount).quantize(Decimal("0.01"))
        return Response({
            "valid": True,
            "code": coupon.code,
            "title": coupon.title,
            "discount_type": coupon.discount_type,
            "discount": str(discount),
            "delivery_discount": str(delivery_discount.quantize(Decimal("0.01"))),
            "message": f'"{coupon.title}" applied! You save Rs.{discount}.',
        })


class CustomerCouponListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CouponSerializer

    def list(self, request, *args, **kwargs):
        return cached_api_response(
            request,
            'orders:customer_coupons',
            120,
            lambda: super(CustomerCouponListView, self).list(request, *args, **kwargs),
            include_user=False,
        )

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
