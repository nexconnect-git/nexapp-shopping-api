from decimal import Decimal

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from delivery.models import DeliveryReview
from orders.models import Order, OrderRating
from orders.serializers import OrderRatingSerializer
from vendors.models import VendorReview


class SubmitOrderRatingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.get(id=pk, customer=request.user)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        if order.status != 'delivered':
            return Response({'error': 'You can only rate delivered orders.'}, status=status.HTTP_400_BAD_REQUEST)
        if hasattr(order, 'rating'):
            return Response({'error': 'You have already rated this order.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OrderRatingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        vendor_rating = data.get('vendor_rating') or data.get('rating')
        delivery_rating = data.get('delivery_rating')
        if order.delivery_partner and delivery_rating is None:
            delivery_rating = data.get('rating')

        if vendor_rating is None:
            return Response({'error': 'Store rating is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if order.delivery_partner and delivery_rating is None:
            return Response({'error': 'Delivery partner rating is required for this order.'}, status=status.HTTP_400_BAD_REQUEST)

        rating_values = [value for value in (vendor_rating, delivery_rating) if value is not None]
        overall_rating = int(round(sum(rating_values) / len(rating_values)))
        rating = OrderRating.objects.create(
            order=order,
            customer=request.user,
            delivery_partner=order.delivery_partner,
            rating=overall_rating,
            vendor_rating=vendor_rating,
            vendor_comment=(data.get('vendor_comment') or '').strip(),
            delivery_rating=delivery_rating,
            delivery_comment=(data.get('delivery_comment') or '').strip(),
        )

        VendorReview.objects.update_or_create(
            vendor=order.vendor,
            customer=request.user,
            defaults={'rating': vendor_rating, 'comment': rating.vendor_comment},
        )

        if order.delivery_partner and delivery_rating is not None:
            try:
                partner = order.delivery_partner.delivery_profile
                DeliveryReview.objects.update_or_create(
                    delivery_partner=partner,
                    order=order,
                    defaults={
                        'customer': request.user,
                        'rating': delivery_rating,
                        'comment': rating.delivery_comment,
                    },
                )
            except Exception:
                pass

        return Response(
            {
                'id': str(rating.id),
                'vendor_rating': rating.vendor_rating,
                'vendor_comment': rating.vendor_comment,
                'delivery_rating': rating.delivery_rating,
                'delivery_comment': rating.delivery_comment,
            },
            status=status.HTTP_201_CREATED,
        )


class TipDeliveryPartnerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.get(id=pk, customer=request.user)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        if order.status != 'delivered':
            return Response({'error': 'You can only tip on delivered orders.'}, status=status.HTTP_400_BAD_REQUEST)
        if not order.delivery_partner:
            return Response({'error': 'No delivery partner assigned.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(str(request.data.get('amount', 0)))
        except Exception:
            return Response({'error': 'Invalid tip amount.'}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({'error': 'Tip amount must be positive.'}, status=status.HTTP_400_BAD_REQUEST)

        order.delivery_tip = amount
        order.save(update_fields=['delivery_tip', 'updated_at'])
        return Response({'delivery_tip': str(order.delivery_tip)})
