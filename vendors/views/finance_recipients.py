from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasAdminPermission
from vendors.actions import GetFinanceRecipientsAction, GetVendorBankSummaryAction, GetPayoutEstimateAction


class AdminFinanceRecipientsView(APIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.view'

    def get(self, request):
        return Response(GetFinanceRecipientsAction().execute())


class AdminVendorBankSummaryView(APIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.view'

    def get(self, request, pk):
        return Response(GetVendorBankSummaryAction().execute(pk))


class AdminPayoutEstimateView(APIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.view'

    def get(self, request, kind, pk):
        return Response(GetPayoutEstimateAction().execute(kind, pk, request.query_params))
