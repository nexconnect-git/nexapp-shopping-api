"""Admin payout views for vendor payouts."""
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from accounts.actions.audit_actions import CreateAdminAuditLogAction
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
        CreateAdminAuditLogAction().execute(
            request=request,
            action='payout',
            entity_type='vendor_payout',
            entity_id=str(payout.id),
            summary=f"Updated vendor payout {payout.id}.",
            metadata=request.data,
        )
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
        CreateAdminAuditLogAction().execute(
            request=request,
            action='payout',
            entity_type='vendor_payout',
            entity_id=str(payout.id),
            summary=f"Scheduled vendor payout {payout.id}.",
            metadata={'status': 'scheduled'},
        )
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
        
        # Only deduct wallet balance if the payout wasn't already Paid
        if payout.status != "paid":
            payout.status = "paid"
            payout.transaction_ref = transaction_ref
            payout.payment_sent_at = timezone.now()
            payout.paid_at = timezone.now()
            payout.save(update_fields=["status", "transaction_ref", "payment_sent_at", "paid_at"])
            
            # Debit Vendor Wallet
            from vendors.actions.wallet_actions import VendorWalletAction
            try:
                VendorWalletAction.debit_vendor(
                    vendor_id=str(payout.vendor.id),
                    amount=payout.net_payout,
                    source='payout_withdrawal',
                    reference_id=str(payout.id),
                    description=f"Withdrawal for Payout to {payout.vendor.store_name}"
                )
            except ValueError:
                pass # Already handled or balance too low

        CreateAdminAuditLogAction().execute(
            request=request,
            action='payout',
            entity_type='vendor_payout',
            entity_id=str(payout.id),
            summary=f"Marked vendor payout {payout.id} as paid.",
            metadata={'status': payout.status, 'transaction_ref': transaction_ref},
        )
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
        CreateAdminAuditLogAction().execute(
            request=request,
            action='payout',
            entity_type='vendor_payout',
            entity_id=str(payout.id),
            summary=f"Force-verified vendor payout {payout.id}.",
            metadata={'status': 'verified'},
        )
        return Response(VendorPayoutSerializer(payout).data)
