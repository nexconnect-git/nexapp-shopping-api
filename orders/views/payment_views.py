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

from helpers.cache_helpers import cached_api_response
from helpers.delivery_quotes import FarDeliveryConfirmationRequired
from orders.actions.checkout import COD_UPI_CONFIRMATION_MESSAGE, calculate_checkout_preview
from orders.actions.payment_actions import CreateRazorpayOrderAction, VerifyRazorpayPaymentAction
from orders.data.order_repo import OrderRepository
from orders.models import PaymentSession, PlatformSetting
from orders.serializers import OrderSerializer
from orders.services.razorpay_service import RazorpayService

logger = logging.getLogger(__name__)


class PaymentMethodsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return cached_api_response(
            request,
            'orders:payment_methods',
            300,
            lambda: self._get_uncached(request),
            include_user=False,
        )

    def _get_uncached(self, request):
        setting = PlatformSetting.get_setting()
        methods = setting.normalized_payment_methods()
        labels = {
            setting.PAYMENT_METHOD_COD: "UPI at Delivery",
            setting.PAYMENT_METHOD_UPI: "UPI",
            setting.PAYMENT_METHOD_CARD: "Cards",
            setting.PAYMENT_METHOD_WALLET: "Wallets",
            setting.PAYMENT_METHOD_NETBANKING: "Netbanking",
        }
        available_methods = [
            {
                "id": method,
                "gateway": "cod" if method == setting.PAYMENT_METHOD_COD else "razorpay",
                "label": labels.get(method, method.replace("_", " ").title()),
                "enabled": True,
                "requires_confirmation": method == setting.PAYMENT_METHOD_COD,
                "confirmation_message": COD_UPI_CONFIRMATION_MESSAGE if method == setting.PAYMENT_METHOD_COD else "",
            }
            for method in methods
        ]
        return Response({
            'enabled_payment_methods': methods,
            'available_methods': available_methods,
            'cod_enabled': setting.PAYMENT_METHOD_COD in methods,
            'online_enabled': any(method.startswith('razorpay_') for method in methods),
        })


class InitiateCheckoutPaymentView(APIView):
    """POST /api/orders/initiate-checkout-payment/

    Creates a Razorpay order for the current cart total **before** the app order
    is created. The frontend opens the Razorpay modal with the returned data;
    on success it includes the payment proof when calling POST /api/orders/create/.

    Body (all optional except delivery_address_id):
        delivery_address_id (uuid): Used to compute delivery fee.
        coupon_code (str):          Applied coupon code.
        wallet_amount (float):      Amount to deduct from wallet.
        confirm_far_delivery (bool): Acknowledge long-distance ordering before payment.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        platform_setting = PlatformSetting.get_setting()
        if not platform_setting.is_online_payment_enabled():
            return Response({'error': 'Online payment is currently disabled.'}, status=status.HTTP_400_BAD_REQUEST)

        if not getattr(settings, 'RAZORPAY_KEY_ID', '') or not getattr(settings, 'RAZORPAY_KEY_SECRET', ''):
            return Response({'error': 'Razorpay is not configured.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            preview = calculate_checkout_preview(
                user=request.user,
                delivery_address_id=request.data.get('delivery_address_id'),
                payment_method='razorpay',
                coupon_code=request.data.get('coupon_code', ''),
                wallet_amount=request.data.get('wallet_amount', 0),
                scheduled_for=request.data.get('scheduled_for'),
                confirm_far_delivery=bool(request.data.get('confirm_far_delivery', False)),
                cod_upi_confirmed=True,
            )
        except FarDeliveryConfirmationRequired as exc:
            return Response(
                {
                    'error': 'Far delivery confirmation required.',
                    'code': 'far_delivery_confirmation_required',
                    'quotes': exc.quotes,
                },
                status=status.HTTP_409_CONFLICT,
            )
        except ValueError as exc:
            payload = exc.args[0] if exc.args else str(exc)
            if isinstance(payload, dict):
                return Response(payload, status=status.HTTP_400_BAD_REQUEST)
            return Response({'error': str(payload)}, status=status.HTTP_400_BAD_REQUEST)

        final_total = preview['final_payable']

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

        PaymentSession.objects.update_or_create(
            gateway_order_id=rz_order['id'],
            defaults={
                'customer': request.user,
                'amount': Decimal(str(final_total)).quantize(Decimal('0.01')),
                'currency': rz_order.get('currency', 'INR'),
                'status': PaymentSession.STATUS_CREATED,
                'metadata': {
                    'delivery_address_id': str(request.data.get('delivery_address_id', '')),
                    'coupon_code': request.data.get('coupon_code', ''),
                    'wallet_amount': str(request.data.get('wallet_amount', 0)),
                },
            },
        )

        return Response({
            'razorpay_order_id': rz_order['id'],
            'amount': rz_order['amount'],
            'currency': rz_order['currency'],
            'key_id': settings.RAZORPAY_KEY_ID,
            'requires_far_delivery_confirmation': False,
        })


class CreateRazorpayOrderView(APIView):
    """POST /api/orders/<pk>/create-payment/

    Creates a Razorpay order for the given Nextou order.
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
            event_id = payload.get('id', '')

            if not rz_order_id:
                return

            from orders.models import Order
            session = PaymentSession.objects.filter(gateway_order_id=rz_order_id).first()
            if session and event_id and session.last_event_id == event_id:
                return

            try:
                order = Order.objects.get(razorpay_order_id=rz_order_id)
            except Order.DoesNotExist:
                if session:
                    session.gateway_payment_id = rz_payment_id
                    session.status = PaymentSession.STATUS_PAID
                    session.last_event_id = event_id
                    session.mismatch_reason = "Payment captured before application order finalization."
                    session.save(update_fields=[
                        'gateway_payment_id',
                        'status',
                        'last_event_id',
                        'mismatch_reason',
                        'updated_at',
                    ])
                logger.warning("Webhook: no order found for razorpay_order_id=%s", rz_order_id)
                return

            if not order.is_payment_verified:
                order.razorpay_payment_id = rz_payment_id
                order.is_payment_verified = True
                order.save(update_fields=['razorpay_payment_id', 'is_payment_verified', 'updated_at'])
                if session:
                    session.gateway_payment_id = rz_payment_id
                    session.status = PaymentSession.STATUS_PAID
                    session.last_event_id = event_id
                    session.save(update_fields=['gateway_payment_id', 'status', 'last_event_id', 'updated_at'])
                    session.orders.add(order)
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
