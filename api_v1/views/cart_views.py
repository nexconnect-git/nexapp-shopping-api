from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api_v1.actions import CartDeliveryQuoteV1Action


class CartDeliveryQuoteV1View(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        result, error, response_status = CartDeliveryQuoteV1Action().execute(
            user=request.user,
            address_id=request.query_params.get('address_id'),
        )
        if error:
            return Response(error, status=response_status)
        return Response(result, status=response_status)
