from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.actions.customer_content_actions import GetCustomerContentConfigAction


class CustomerContentConfigView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(GetCustomerContentConfigAction().execute())
