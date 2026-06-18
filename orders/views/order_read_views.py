from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.actions.ordering import CancelOrderAction
from orders.data.order_repo import OrderRepository
from orders.models import Order
from orders.serializers import OrderSerializer, OrderTrackingSerializer


class OrderListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return OrderRepository.get_customer_orders(
            self.request.user,
            self.request.query_params.get('status'),
        )

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data = {
            'count': len(response.data) if isinstance(response.data, list) else response.data.get('count', 0),
            'results': response.data if isinstance(response.data, list) else response.data.get('results', response.data),
            'summary': OrderRepository.get_customer_order_summary(request.user),
        }
        return response


class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).prefetch_related('items', 'tracking')


class CancelOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            order = CancelOrderAction().execute(str(pk), request.user)
            return Response(OrderSerializer(order).data)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class OrderTrackingView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderTrackingSerializer

    def get_queryset(self):
        return OrderRepository.get_tracking(self.kwargs['pk'], self.request.user)
