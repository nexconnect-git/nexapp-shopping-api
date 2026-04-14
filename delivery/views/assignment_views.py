from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from delivery.actions.delivery_actions import (
    AcceptDeliveryAction,
    UpdateDeliveryStatusAction,
    ConfirmDeliveryAction,
)
from delivery.actions.assignment_actions import (
    AcceptAssignmentAction,
    RejectAssignmentAction,
    CancelAssignmentAction,
)
from delivery.serializers import DeliveryAssignmentSerializer
from orders.serializers import OrderSerializer
from delivery.tasks import check_assignment_timeout, check_stale_assignments
from delivery.data.assignment_repo import DeliveryAssignmentRepository


class AcceptDeliveryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            order = AcceptDeliveryAction.execute(str(pk), request.user)
            return Response(OrderSerializer(order).data)
        except ValueError as exc:
            if "not found" in str(exc).lower():
                return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class UpdateDeliveryStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        new_status = request.data.get("status")
        try:
            order = UpdateDeliveryStatusAction.execute(str(pk), new_status, request.user)
            return Response(OrderSerializer(order).data)
        except ValueError as exc:
            if "not found" in str(exc).lower():
                return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ConfirmDeliveryView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, pk):
        submitted_otp = str(request.data.get("otp", "")).strip()
        photo = request.FILES.get("photo") or request.FILES.get("delivery_photo")
        transaction_photo = request.FILES.get("transaction_photo")

        try:
            order = ConfirmDeliveryAction.execute(str(pk), request.user, submitted_otp, photo, transaction_photo=transaction_photo)
            return Response(OrderSerializer(order).data)
        except ValueError as exc:
            if "not found" in str(exc).lower():
                return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class PendingAssignmentRequestsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        partner = request.user.delivery_profile

        expired_assignments = DeliveryAssignmentRepository.get_expired_for_partner(partner, minutes_old=1)
        for assignment in expired_assignments:
            check_assignment_timeout(str(assignment.id))

        check_stale_assignments()

        pending_qs = DeliveryAssignmentRepository.get_pending_for_partner(
            partner=partner,
            exclude_rejected=True,
            select_related=["order__vendor"],
            prefetch=["order__items"]
        )
        return Response(DeliveryAssignmentSerializer(pending_qs, many=True).data)


class AcceptAssignmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        try:
            order = AcceptAssignmentAction.execute(str(assignment_id), request.user)
            return Response({"status": "accepted", "order": OrderSerializer(order).data})
        except ValueError as exc:
            if "not found" in str(exc).lower():
                return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)


class RejectAssignmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        try:
            rejected = RejectAssignmentAction.execute(str(assignment_id), request.user)
            if rejected:
                return Response({"status": "rejected"})
            return Response({"status": "ok"})
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)


class CancelAssignmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            CancelAssignmentAction.execute(str(pk), request.user)
            return Response({"status": "cancelled"})
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
