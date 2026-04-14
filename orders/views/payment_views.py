"""Payment views — Razorpay order creation, payment verification, and webhooks."""

import json
import logging

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.actions.payment_actions import CreateRazorpayOrderAction, VerifyRazorpayPaymentAction
from orders.data.order_repo import OrderRepository
from orders.serializers import OrderSerializer
from orders.services.razorpay_service import RazorpayService

logger = logging.getLogger(__name__)


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

        if order.status not in ('placed', 'confirmed'):
            return Response(
                {'error': f"Cannot initiate payment for an order with status '{order.status}'."},
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
