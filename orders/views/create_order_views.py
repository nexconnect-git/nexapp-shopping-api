from decimal import Decimal

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from helpers.delivery_quotes import DeliveryServiceabilityError, FarDeliveryConfirmationRequired
from orders.actions.ordering import CreateOrdersFromCartAction
from orders.models import Order, PaymentSession, PlatformSetting
from orders.serializers import CreateOrderSerializer, OrderSerializer


class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        razorpay_order_id = data.get('razorpay_order_id', '').strip()
        razorpay_payment_id = data.get('razorpay_payment_id', '').strip()
        razorpay_signature = data.get('razorpay_signature', '').strip()
        has_razorpay_proof = bool(razorpay_order_id and razorpay_payment_id and razorpay_signature)
        payment_method = data.get('payment_method', 'cod')

        payment_error = self._validate_payment_method(payment_method, has_razorpay_proof)
        if payment_error:
            return payment_error
        signature_error = self._verify_razorpay_signature(
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature,
            has_razorpay_proof,
        )
        if signature_error:
            return signature_error

        try:
            with transaction.atomic():
                payment_session = self._lock_payment_session(
                    request,
                    razorpay_order_id,
                    has_razorpay_proof,
                )
                if isinstance(payment_session, Response):
                    return payment_session

                created_orders = CreateOrdersFromCartAction().execute(
                    user=request.user,
                    delivery_address_id=data['delivery_address_id'],
                    payment_method=payment_method,
                    notes=data.get('notes', ''),
                    coupon_code=data.get('coupon_code', '').strip().upper(),
                    wallet_amount=data.get('wallet_amount', Decimal('0')),
                    loyalty_points=data.get('loyalty_points', 0),
                    scheduled_for=data.get('scheduled_for'),
                    confirm_far_delivery=data.get('confirm_far_delivery', False),
                    cod_upi_confirmed=data.get('cod_upi_confirmed', False),
                    client_price_breakup=data.get('client_price_breakup', {}),
                    client_idempotency_key=(
                        data.get('client_idempotency_key', '').strip()
                        or request.headers.get('Idempotency-Key', '').strip()
                    ),
                )

                if has_razorpay_proof:
                    self._attach_paid_session(
                        payment_session,
                        created_orders,
                        razorpay_order_id,
                        razorpay_payment_id,
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
        except DeliveryServiceabilityError as exc:
            return Response(
                {
                    'error': str(exc),
                    'code': 'delivery_not_serviceable',
                    'details': exc.quote.as_dict(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as exc:
            payload = exc.args[0] if exc.args else str(exc)
            if has_razorpay_proof and str(payload).startswith('Payment amount mismatch'):
                PaymentSession.objects.filter(
                    gateway_order_id=razorpay_order_id,
                    customer=request.user,
                ).update(
                    status=PaymentSession.STATUS_FAILED,
                    mismatch_reason=str(payload),
                )
            if isinstance(payload, dict):
                return Response(payload, status=status.HTTP_400_BAD_REQUEST)
            return Response({'error': str(payload)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(OrderSerializer(created_orders, many=True).data, status=status.HTTP_201_CREATED)

    def _validate_payment_method(self, payment_method, has_razorpay_proof):
        platform_setting = PlatformSetting.get_setting()
        if payment_method == 'cod' and not platform_setting.is_cod_enabled():
            return Response({'error': 'Cash on delivery is currently disabled.'}, status=status.HTTP_400_BAD_REQUEST)
        if payment_method == 'razorpay' and not platform_setting.is_online_payment_enabled():
            return Response({'error': 'Online payment is currently disabled.'}, status=status.HTTP_400_BAD_REQUEST)
        if payment_method == 'razorpay' and not has_razorpay_proof:
            return Response(
                {'error': 'Online payment was not completed. Please finish payment before placing the order.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    def _verify_razorpay_signature(self, razorpay_order_id, razorpay_payment_id, razorpay_signature, has_razorpay_proof):
        if not has_razorpay_proof:
            return None
        from orders.services.razorpay_service import RazorpayService

        if RazorpayService().verify_payment_signature(
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
        ):
            return None
        return Response({'error': 'Payment verification failed. Please try payment again.'}, status=status.HTTP_400_BAD_REQUEST)

    def _lock_payment_session(self, request, razorpay_order_id, has_razorpay_proof):
        if not has_razorpay_proof:
            return None
        try:
            payment_session = PaymentSession.objects.select_for_update().get(
                gateway_order_id=razorpay_order_id,
                customer=request.user,
            )
        except PaymentSession.DoesNotExist:
            return Response({'error': 'Payment session not found. Please restart checkout.'}, status=status.HTTP_400_BAD_REQUEST)

        if payment_session.status == PaymentSession.STATUS_PAID and payment_session.orders.exists():
            existing_orders = payment_session.orders.select_related(
                'vendor',
                'delivery_address',
                'delivery_partner',
            ).prefetch_related('items', 'tracking').all()
            return Response(OrderSerializer(existing_orders, many=True).data)
        return payment_session

    def _attach_paid_session(self, payment_session, created_orders, razorpay_order_id, razorpay_payment_id):
        created_total = sum((order.total for order in created_orders), Decimal('0')).quantize(Decimal('0.01'))
        if created_total != payment_session.amount:
            payment_session.status = PaymentSession.STATUS_FAILED
            payment_session.mismatch_reason = f'Payment amount {payment_session.amount} did not match order total {created_total}.'
            payment_session.save(update_fields=['status', 'mismatch_reason', 'updated_at'])
            raise ValueError('Payment amount mismatch. Please restart checkout.')
        Order.objects.filter(pk__in=[order.pk for order in created_orders]).update(
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            is_payment_verified=True,
        )
        for order in created_orders:
            order.razorpay_order_id = razorpay_order_id
            order.razorpay_payment_id = razorpay_payment_id
            order.is_payment_verified = True
        payment_session.gateway_payment_id = razorpay_payment_id
        payment_session.status = PaymentSession.STATUS_PAID
        payment_session.save(update_fields=['gateway_payment_id', 'status', 'updated_at'])
        payment_session.orders.set(created_orders)
