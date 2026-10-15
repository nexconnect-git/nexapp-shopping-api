from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.actions import ReorderAction
from orders.serializers import CartSerializer


class ReorderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            result = ReorderAction().execute(request.user, pk, preview=request.data.get('preview') is True)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        cart = result.pop('cart', None)
        if cart is None:
            return Response(result)
        return Response({**CartSerializer(cart).data, 'reorder_changes': result['items'], 'skipped': result['skipped']})
