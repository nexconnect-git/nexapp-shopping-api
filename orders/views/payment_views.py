"""Payment views — Razorpay order creation, payment verification, and webhooks."""

import json
import logging
from decimal import Decimal

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Address
from helpers.geo_helpers import haversine
from orders.actions.payment_actions import CreateRazorpayOrderAction, VerifyRazorpayPaymentAction
from orders.data.order_repo import OrderRepository
from orders.serializers import OrderSerializer
from orders.services.razorpay_service import RazorpayService

logger = logging.getLogger(__name__)


class InitiateCheckoutPaymentView(APIView):
    """POST /api/orders/initiate-checkout-payment/

    Creates a Razorpay order for the current cart total **before** the app order
    is created. The frontend opens the Razorpay modal with the returned data;
    on success it includes the payment proof when calling POST /api/orders/create/.

    Body (all optional except delivery_address_id):
        delivery_address_id (uuid): Used to compute delivery fee.
        coupon_code (str):          Applied coupon code.
        wallet_amount (float):      Amount to deduct from wallet.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not getattr(settings, 'RAZORPAY_KEY_ID', ''):
            return Response({'error': 'Razorpay is not configured.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        from orders.models import Cart
        from orders.models.setting import PlatformSetting
        from orders.models.coupon import Coupon

        try:
            cart = Cart.objects.prefetch_related('items__product__vendor').get(user=request.user)
        except Cart.DoesNotExist:
            return Response({'error': 'Cart is empty.'}, status=status.HTTP_400_BAD_REQUEST)

        if not cart.items.exists():
            return Response({'error': 'Cart is empty.'}, status=status.HTTP_400_BAD_REQUEST)

        cart_total = Decimal(str(cart.total_amount))

        # Compute delivery fee from address
        delivery_fee = Decimal('0')
        address_id = request.data.get('delivery_address_id')
        if address_id:
            try:
                delivery_address = Address.objects.get(pk=address_id, user=request.user)
                platform = PlatformSetting.get_setting()
                vendor_seen: set = set()
                for item in cart.items.select_related('product__vendor').all():
                    vendor = item.product.vendor
                    if vendor.id in vendor_seen:
                        continue
                    vendor_seen.add(vendor.id)
                    subtotal = sum(
                        ci.product.price * ci.quantity
                        for ci in cart.items.all()
                        if ci.product.vendor_id == vendor.id
                    )
                    if platform.free_delivery_above > 0 and subtotal >= platform.free_delivery_above:
                        continue
                    distance = 0.0
                    if delivery_address.latitude and delivery_address.longitude:
                        distance = haversine(
                            float(vendor.latitude), float(vendor.longitude),
                            float(delivery_address.latitude), float(delivery_address.longitude),
                        )
                    delivery_fee += (
                        platform.delivery_base_fee
                        + platform.delivery_per_km_fee * Decimal(str(round(distance, 2)))
                    )
            except Address.DoesNotExist:
                pass

        # Coupon discount
        coupon_discount = Decimal('0')
        coupon_code = (request.data.get('coupon_code') or '').strip().upper()
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code, is_active=True)
                if coupon.discount_type == 'percentage':
                    coupon_discount = (cart_total * coupon.discount_value / 100).quantize(Decimal('0.01'))
                else:
                    coupon_discount = min(coupon.discount_value, cart_total)
            except Coupon.DoesNotExist:
                pass

        # Wallet deduction
        wallet_amount = Decimal(str(request.data.get('wallet_amount', 0) or 0))

        final_total = max(cart_total + delivery_fee - coupon_discount - wallet_amount, Decimal('0'))

        if final_total <= 0:
            return Response(
                {'error': 'Total is fully covered by wallet — place order directly without online payment.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            rz_order = RazorpayService().create_order(
                amount_inr=float(final_total),
                receipt='checkout',
            )
        except Exception as exc:
            logger.error("Failed to create Razorpay order for checkout: %s", exc)
            return Response({'error': 'Could not initiate payment. Please try again.'}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            'razorpay_order_id': rz_order['id'],
            'amount': rz_order['amount'],
            'currency': rz_order['currency'],
            'key_id': settings.RAZORPAY_KEY_ID,
        })


class CreateRazorpayOrderView(APIView):
    """POST /api/orders/<pk>/create-payment/

    Creates a Razorpay order for the given NexConnect order.
    Returns the data needed to open the Razorpay checkout modal on the frontend.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = OrderRepository().get_by_id(pk)
        if not order or order.customer != request.user:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        if order.status in ('delivered', 'cancelled'):
            return Response(
                {'error': f"Cannot initiate payment for a {order.status} order."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = CreateRazorpayOrderAction(order).execute()
            return Response(result)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class VerifyRazorpayPaymentView(APIView):
    """POST /api/orders/<pk>/verify-payment/

    Verifies the Razorpay payment signature after the frontend checkout completes.
    On success, marks the order payment as verified.

    Expected body:
        razorpay_payment_id: str
        razorpay_signature:  str
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = OrderRepository().get_by_id(pk)
        if not order or order.customer != request.user:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        payment_id = request.data.get('razorpay_payment_id', '').strip()
        signature = request.data.get('razorpay_signature', '').strip()

        if not payment_id or not signature:
            return Response(
                {'error': 'razorpay_payment_id and razorpay_signature are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            updated_order = VerifyRazorpayPaymentAction(order, payment_id, signature).execute()
            return Response(OrderSerializer(updated_order).data)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class RazorpayWebhookView(APIView):
    """POST /api/orders/razorpay-webhook/

    Receives Razorpay payment events and marks orders as paid automatically.
    The ``X-Razorpay-Signature`` header is verified against RAZORPAY_WEBHOOK_SECRET.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        signature = request.headers.get('X-Razorpay-Signature', '')
        payload_body = request.body

        if not RazorpayService().verify_webhook_signature(payload_body, signature):
            logger.warning("Razorpay webhook: invalid signature")
            return Response({'error': 'Invalid signature.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = json.loads(payload_body)
        except json.JSONDecodeError:
            return Response({'error': 'Invalid JSON.'}, status=status.HTTP_400_BAD_REQUEST)

        event = payload.get('event', '')
        if event == 'payment.captured':
            self._handle_payment_captured(payload)
        elif event == 'refund.processed':
            self._handle_refund_event(payload, 'processed')
        elif event == 'refund.failed':
            self._handle_refund_event(payload, 'failed')

        return Response({'status': 'ok'})

    @staticmethod
    def _handle_payment_captured(payload: dict) -> None:
        """Mark the order as payment-verified when Razorpay confirms capture."""
        try:
            payment = payload['payload']['payment']['entity']
            rz_order_id = payment.get('order_id', '')
            rz_payment_id = payment.get('id', '')

            if not rz_order_id:
                return

            from orders.models import Order
            try:
                order = Order.objects.get(razorpay_order_id=rz_order_id)
            except Order.DoesNotExist:
                logger.warning("Webhook: no order found for razorpay_order_id=%s", rz_order_id)
                return

            if not order.is_payment_verified:
                order.razorpay_payment_id = rz_payment_id
                order.is_payment_verified = True
                order.save(update_fields=['razorpay_payment_id', 'is_payment_verified', 'updated_at'])
                logger.info("Webhook: payment verified for order %s", order.order_number)
        except (KeyError, TypeError) as exc:
            logger.error("Webhook payload parse error: %s", exc)

    @staticmethod
    def _handle_refund_event(payload: dict, new_status: str) -> None:
        """Update refund_status on the order when Razorpay confirms or fails a refund."""
        try:
            refund = payload['payload']['refund']['entity']
            refund_id = refund.get('id', '')
            if not refund_id:
                return

            from orders.models import Order
            try:
                order = Order.objects.get(razorpay_refund_id=refund_id)
            except Order.DoesNotExist:
                logger.warning("Webhook: no order found for razorpay_refund_id=%s", refund_id)
                return

            order.refund_status = new_status
            order.save(update_fields=['refund_status', 'updated_at'])
            logger.info("Webhook: refund %s for order %s", new_status, order.order_number)
        except (KeyError, TypeError) as exc:
            logger.error("Refund webhook parse error: %s", exc)
