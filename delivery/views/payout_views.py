"""
Delivery partner payout views — both partner self-service and admin management.
Uses DeliveryPartnerPayout model stored in the vendors app.
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.actions.audit_actions import CreateAdminAuditLogAction
from accounts.permissions import HasAdminPermission
from vendors.actions import CreateAdminPayoutAction, DeclineDeliveryPayoutAction, UpdateAdminPayoutAction
from vendors.models import DeliveryPartnerPayout
from vendors.serializers import DeliveryPartnerPayoutSerializer


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# ---------------------------------------------------------------------------
# Partner self-service
# ---------------------------------------------------------------------------

class DeliveryPayoutListView(APIView):
    """GET /api/delivery/payouts/ — list the authenticated partner's payouts."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = DeliveryPartnerPayout.objects.filter(
            delivery_partner=request.user
        ).order_by("-period_start")
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            DeliveryPartnerPayoutSerializer(page, many=True).data
        )


class DeliveryPayoutApproveView(APIView):
    """POST /api/delivery/payouts/<pk>/approve/ — partner approves a payout."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            payout = DeliveryPartnerPayout.objects.get(pk=pk, delivery_partner=request.user)
        except DeliveryPartnerPayout.DoesNotExist:
            return Response({"error": "Payout not found."}, status=status.HTTP_404_NOT_FOUND)

        if payout.status != "pending_approval":
            return Response(
                {"error": f"Cannot approve a payout with status '{payout.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payout.status = "approved"
        payout.partner_approved_at = timezone.now()
        payout.save(update_fields=["status", "partner_approved_at"])
        return Response(DeliveryPartnerPayoutSerializer(payout).data)


class DeliveryPayoutDeclineView(APIView):
    """POST /api/delivery/payouts/<pk>/decline/ — partner declines a payout."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        payout = DeclineDeliveryPayoutAction().execute(pk, request.data.get('reason', ''), request)
        return Response(DeliveryPartnerPayoutSerializer(payout).data)


class DeliveryPayoutVerifyCreditView(APIView):
    """POST /api/delivery/payouts/<pk>/verify-credit/ — partner confirms receipt."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            payout = DeliveryPartnerPayout.objects.get(pk=pk, delivery_partner=request.user)
        except DeliveryPartnerPayout.DoesNotExist:
            return Response({"error": "Payout not found."}, status=status.HTTP_404_NOT_FOUND)

        if payout.status != "paid":
            return Response(
                {"error": "Can only verify a payout that has been marked as paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payout.status = "verified"
        payout.partner_verified_at = timezone.now()
        payout.save(update_fields=["status", "partner_verified_at"])
        return Response(DeliveryPartnerPayoutSerializer(payout).data)


# ---------------------------------------------------------------------------
# Admin management
# ---------------------------------------------------------------------------

class AdminDeliveryPayoutListView(APIView):
    """GET /api/admin/payouts/delivery/ — list all delivery payouts."""
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.manage'

    def post(self, request):
        payout = CreateAdminPayoutAction().execute('delivery', request.data, request)
        return Response(DeliveryPartnerPayoutSerializer(payout).data, status=status.HTTP_201_CREATED)

    def get(self, request):
        qs = DeliveryPartnerPayout.objects.select_related(
            "delivery_partner"
        ).order_by("-period_start")

        partner_id = request.query_params.get("partner")
        if partner_id:
            qs = qs.filter(delivery_partner_id=partner_id)

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            DeliveryPartnerPayoutSerializer(page, many=True).data
        )


class AdminDeliveryPayoutDetailView(APIView):
    """GET/PATCH /api/admin/payouts/delivery/<pk>/ — retrieve or update a payout."""
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.manage'

    def _get(self, pk):
        try:
            return DeliveryPartnerPayout.objects.select_related("delivery_partner").get(pk=pk)
        except DeliveryPartnerPayout.DoesNotExist:
            return None

    def get(self, request, pk):
        payout = self._get(pk)
        if not payout:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(DeliveryPartnerPayoutSerializer(payout).data)

    def patch(self, request, pk):
        payout = UpdateAdminPayoutAction().execute('delivery', pk, 'edit', request.data, request=request)
        return Response(DeliveryPartnerPayoutSerializer(payout).data)


class AdminDeliveryPayoutScheduleView(APIView):
    """POST /api/admin/payouts/delivery/<pk>/schedule/ — mark payout as scheduled."""
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.manage'

    def post(self, request, pk):
        payout = UpdateAdminPayoutAction().execute('delivery', pk, 'schedule', request.data, request=request)
        return Response(DeliveryPartnerPayoutSerializer(payout).data)


class AdminDeliveryPayoutSendPaymentView(APIView):
    """POST /api/admin/payouts/delivery/<pk>/send-payment/ — mark payment sent."""
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.manage'

    def post(self, request, pk):
        payout = UpdateAdminPayoutAction().execute('delivery', pk, 'record_payment', request.data, request=request)
        return Response(DeliveryPartnerPayoutSerializer(payout).data)


class AdminDeliveryPayoutForcePaidView(APIView):
    """POST /api/admin/payouts/delivery/<pk>/force-paid/ — force payout to verified."""
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.manage'

    def post(self, request, pk):
        payout = UpdateAdminPayoutAction().execute('delivery', pk, 'verify_override', request.data, request=request)
        return Response(DeliveryPartnerPayoutSerializer(payout).data)
