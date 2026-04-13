"""Admin payout views for vendor payouts."""
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from vendors.models import VendorPayout
from vendors.serializers import VendorPayoutSerializer


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminVendorPayoutListView(APIView):
    """GET /api/admin/payouts/vendors/ — list all vendor payouts."""
    permission_classes = [IsAuthenticated, IsAdminRole]

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
    permission_classes = [IsAuthenticated, IsAdminRole]

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
        payout = self._get(pk)
        if not payout:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = VendorPayoutSerializer(payout, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AdminVendorPayoutScheduleView(APIView):
    """POST /api/admin/payouts/vendors/<pk>/schedule/ — mark payout as scheduled."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        try:
            payout = VendorPayout.objects.get(pk=pk)
        except VendorPayout.DoesNotExist:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        payout.status = "scheduled"
        payout.save(update_fields=["status"])
        return Response(VendorPayoutSerializer(payout).data)


class AdminVendorPayoutSendPaymentView(APIView):
    """POST /api/admin/payouts/vendors/<pk>/send-payment/ — mark payment as sent."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        try:
            payout = VendorPayout.objects.get(pk=pk)
        except VendorPayout.DoesNotExist:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        transaction_ref = request.data.get("transaction_ref", "")
        payout.status = "paid"
        payout.transaction_ref = transaction_ref
        payout.payment_sent_at = timezone.now()
        payout.paid_at = timezone.now()
        payout.save(update_fields=["status", "transaction_ref", "payment_sent_at", "paid_at"])
        return Response(VendorPayoutSerializer(payout).data)


class AdminVendorPayoutForcePaidView(APIView):
    """POST /api/admin/payouts/vendors/<pk>/force-paid/ — force payout to verified."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        try:
            payout = VendorPayout.objects.get(pk=pk)
        except VendorPayout.DoesNotExist:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        payout.status = "verified"
        payout.vendor_verified_at = timezone.now()
        payout.save(update_fields=["status", "vendor_verified_at"])
        return Response(VendorPayoutSerializer(payout).data)
