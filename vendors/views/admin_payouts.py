"""Admin payout views for vendor payouts."""
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasAdminPermission
from vendors.actions import CreateAdminPayoutAction, UpdateAdminPayoutAction
from accounts.actions.audit_actions import CreateAdminAuditLogAction
from vendors.models import VendorPayout
from vendors.serializers import VendorPayoutSerializer


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminVendorPayoutListView(APIView):
    """GET /api/admin/payouts/vendors/ — list all vendor payouts."""
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.manage'

    def post(self, request):
        payout = CreateAdminPayoutAction().execute('vendor', request.data, request)
        return Response(VendorPayoutSerializer(payout).data, status=status.HTTP_201_CREATED)

    def get(self, request):
        qs = VendorPayout.objects.select_related("vendor").order_by("-period_start")

        vendor_id = request.query_params.get("vendor")
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            VendorPayoutSerializer(page, many=True).data
        )


class AdminVendorPayoutDetailView(APIView):
    """GET/PATCH /api/admin/payouts/vendors/<pk>/ — retrieve or update a payout."""
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.manage'

    def _get(self, pk):
        try:
            return VendorPayout.objects.select_related("vendor").get(pk=pk)
        except VendorPayout.DoesNotExist:
            return None

    def get(self, request, pk):
        payout = self._get(pk)
        if not payout:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(VendorPayoutSerializer(payout).data)

    def patch(self, request, pk):
        payout = UpdateAdminPayoutAction().execute('vendor', pk, 'edit', request.data, request=request)
        return Response(VendorPayoutSerializer(payout).data)


class AdminVendorPayoutScheduleView(APIView):
    """POST /api/admin/payouts/vendors/<pk>/schedule/ — mark payout as scheduled."""
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.manage'

    def post(self, request, pk):
        payout = UpdateAdminPayoutAction().execute('vendor', pk, 'schedule', request.data, request=request)
        return Response(VendorPayoutSerializer(payout).data)


class AdminVendorPayoutSendPaymentView(APIView):
    """POST /api/admin/payouts/vendors/<pk>/send-payment/ — mark payment as sent."""
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.manage'

    def post(self, request, pk):
        payout = UpdateAdminPayoutAction().execute('vendor', pk, 'record_payment', request.data, request=request)
        return Response(VendorPayoutSerializer(payout).data)


class AdminVendorPayoutForcePaidView(APIView):
    """POST /api/admin/payouts/vendors/<pk>/force-paid/ — force payout to verified."""
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.manage'

    def post(self, request, pk):
        payout = UpdateAdminPayoutAction().execute('vendor', pk, 'verify_override', request.data, request=request)
        return Response(VendorPayoutSerializer(payout).data)
