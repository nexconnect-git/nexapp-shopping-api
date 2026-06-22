from decimal import Decimal

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Address
from helpers.delivery_quotes import DeliveryServiceabilityError, FarDeliveryConfirmationRequired, quote_vendor_delivery
from orders.actions.checkout import available_slots_for_cart, calculate_checkout_preview, public_price_breakup
from orders.models import Cart
from orders.models.setting import PlatformSetting


class CancellationPolicyView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        setting = PlatformSetting.get_setting()
        return Response({
            'window_minutes': setting.cancellation_window_minutes,
            'allowed_statuses': ['placed', 'confirmed', 'preparing', 'ready'],
        })


class DeliveryFeePreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        address_id = request.query_params.get('address_id')
        if not address_id:
            return Response({'error': 'address_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            delivery_address = Address.objects.get(pk=address_id, user=request.user)
        except Address.DoesNotExist:
            return Response({'error': 'Address not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            cart = Cart.objects.prefetch_related('items__product__vendor').get(user=request.user)
        except Cart.DoesNotExist:
            return Response({'fees': [], 'total_delivery_fee': '0.00'})

        platform = PlatformSetting.get_setting()
        vendor_seen = {}
        fees = []
        far_delivery_quotes = []
        cart_items = list(cart.items.select_related('product__vendor').all())

        for item in cart_items:
            vendor = item.product.vendor
            if vendor.id in vendor_seen:
                continue
            vendor_seen[vendor.id] = True

            vendor_items = [cart_item for cart_item in cart_items if cart_item.product.vendor_id == vendor.id]
            subtotal = sum(cart_item.product.price * cart_item.quantity for cart_item in vendor_items)
            quote = quote_vendor_delivery(
                vendor=vendor,
                address=delivery_address,
                products=[cart_item.product for cart_item in vendor_items],
                quantities={str(cart_item.product.id): cart_item.quantity for cart_item in vendor_items},
                subtotal=subtotal,
                platform=platform,
            )
            payload = quote.as_dict()
            if platform.free_delivery_above > 0 and subtotal >= platform.free_delivery_above:
                payload['delivery_fee'] = '0.00'
                payload['reason'] = f'Free delivery on orders above Rs {platform.free_delivery_above}'
            else:
                payload['reason'] = f"Distance-based delivery for {round(payload['distance_km'], 1)} km"
            fees.append(payload)
            if quote.requires_far_delivery_confirmation:
                far_delivery_quotes.append(payload)

        total = sum((Decimal(fee['delivery_fee']) for fee in fees), Decimal('0.00'))
        return Response(
            {
                'fees': fees,
                'total_delivery_fee': str(total.quantize(Decimal('0.01'))),
                'free_delivery_above': str(platform.free_delivery_above),
                'requires_far_delivery_confirmation': bool(far_delivery_quotes),
                'far_delivery_quotes': far_delivery_quotes,
            }
        )


class CheckoutPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            preview = calculate_checkout_preview(
                user=request.user,
                delivery_address_id=request.data.get('delivery_address_id'),
                payment_method=request.data.get('payment_method', 'cod'),
                coupon_code=request.data.get('coupon_code', ''),
                wallet_amount=request.data.get('wallet_amount', Decimal('0')),
                scheduled_for=request.data.get('scheduled_for'),
                confirm_far_delivery=bool(request.data.get('confirm_far_delivery', False)),
                cod_upi_confirmed=bool(request.data.get('cod_upi_confirmed', False)),
                require_cod_confirmation=False,
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
            if isinstance(payload, dict):
                return Response(payload, status=status.HTTP_400_BAD_REQUEST)
            return Response({'error': str(payload)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'price_breakup': public_price_breakup(preview),
            'delivery_quotes': preview['delivery_quotes'],
            'requires_far_delivery_confirmation': preview['requires_far_delivery_confirmation'],
            'far_delivery_quotes': preview['far_delivery_quotes'],
            'cod_upi_confirmation_required': preview['cod_upi_confirmation_required'],
            'cod_upi_confirmed': preview['cod_upi_confirmed'],
            'cod_upi_message': preview['cod_upi_message'],
        })


class AvailableSlotsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            slots = available_slots_for_cart(
                request.user,
                start_date=request.query_params.get('date'),
                days=min(int(request.query_params.get('days', 7)), 14),
            )
        except ValueError as exc:
            payload = exc.args[0] if exc.args else str(exc)
            if isinstance(payload, dict):
                return Response(payload, status=status.HTTP_400_BAD_REQUEST)
            return Response({'error': str(payload)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'results': slots})
