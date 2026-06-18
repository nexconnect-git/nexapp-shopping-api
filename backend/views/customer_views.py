from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.actions import (
    GetCustomerActiveOrderAction,
    GetCustomerBestCouponAction,
    GetCustomerBuyAgainAction,
    GetCustomerCartSuggestionsAction,
    GetCustomerCheckoutSlotsAction,
    GetCustomerExploreAction,
    GetCustomerFlowHomeAction,
    GetCustomerOrderConfirmationAction,
)


class CustomerHomeView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(GetCustomerFlowHomeAction().execute(request))


class CustomerServiceabilityView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(GetCustomerFlowHomeAction().serviceability_payload(request))

    def post(self, request):
        return Response(GetCustomerFlowHomeAction().serviceability_payload(request))


class CustomerExploreView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(GetCustomerExploreAction().execute(request))


class CustomerBuyAgainView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(GetCustomerBuyAgainAction().execute(request))


class CustomerCartSuggestionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(GetCustomerCartSuggestionsAction().execute(request))


class CustomerBestCouponView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(GetCustomerBestCouponAction().execute(request))

    def post(self, request):
        return Response(GetCustomerBestCouponAction().execute(request))


class CustomerCheckoutSlotsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(GetCustomerCheckoutSlotsAction().execute(request))


class CustomerActiveOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(GetCustomerActiveOrderAction().execute(request))


class CustomerOrderConfirmationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        return Response(GetCustomerOrderConfirmationAction().execute(request, pk))
