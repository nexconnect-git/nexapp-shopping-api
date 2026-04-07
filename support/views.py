"""
API views for the ``support`` app.

Endpoints covered:
  - Vendor: create and list own support tickets, view a single ticket
  - Admin: list all tickets, respond to a ticket
"""

from django.utils import timezone

from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole, IsApprovedVendor
from notifications.models import Notification
from support.models import SupportTicket
from support.serializers import SupportTicketSerializer


class VendorTicketListCreateView(APIView):
    """GET/POST /api/support/tickets/ — vendor creates or lists own support tickets."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request):
        """Return all support tickets belonging to the current vendor.

        Args:
            request: Authenticated DRF request from an approved vendor.

        Returns:
            200 with a list of ticket objects.
        """
        tickets = SupportTicket.objects.filter(vendor=request.user.vendor_profile)
        return Response(SupportTicketSerializer(tickets, many=True).data)

    def post(self, request):
        """Create a new support ticket for the current vendor.

        Args:
            request: Authenticated DRF request with ticket payload.

        Returns:
            201 with the new ticket data, or 400 on validation failure.
        """
        serializer = SupportTicketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(vendor=request.user.vendor_profile)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class VendorTicketDetailView(APIView):
    """GET /api/support/tickets/<pk>/ — vendor views a single support ticket."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request, pk):  # noqa: ARG002
        """Return a single ticket belonging to the current vendor.

        Args:
            request: Authenticated DRF request from an approved vendor.
            pk: UUID primary key of the ticket.

        Returns:
            200 with ticket data, or 404.
        """
        try:
            ticket = SupportTicket.objects.get(pk=pk, vendor=request.user.vendor_profile)
        except SupportTicket.DoesNotExist:
            return Response(
                {"error": "Ticket not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(SupportTicketSerializer(ticket).data)


class AdminTicketListView(generics.ListAPIView):
    """GET /api/admin/support/tickets/ — admin lists all support tickets."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = SupportTicketSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        """Return all tickets ordered by newest first, optionally filtered by status.

        Query params:
            status: Filter by ticket status string.

        Returns:
            Filtered queryset with ``vendor`` select_related.
        """
        qs = SupportTicket.objects.select_related("vendor").order_by("-created_at")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class AdminTicketRespondView(APIView):
    """PATCH /api/admin/support/tickets/<pk>/respond/ — admin responds to a ticket."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def patch(self, request, pk):
        """Add an admin response to a support ticket and notify the vendor.

        Args:
            request: Authenticated admin DRF request with ``admin_response``
                and optional ``status`` fields.
            pk: UUID primary key of the ticket.

        Returns:
            200 with updated ticket data, or 400/404 on error.
        """
        try:
            ticket = SupportTicket.objects.get(pk=pk)
        except SupportTicket.DoesNotExist:
            return Response(
                {"error": "Ticket not found."}, status=status.HTTP_404_NOT_FOUND
            )

        response_text = request.data.get("admin_response", "").strip()
        new_status = request.data.get("status", "in_progress")
        if not response_text:
            return Response(
                {"error": "admin_response is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ticket.admin_response = response_text
        ticket.status = new_status
        ticket.responded_by = request.user
        ticket.responded_at = timezone.now()
        ticket.save()

        Notification.objects.create(
            user=ticket.vendor.user,
            title="Support Ticket Updated",
            message=f'Your ticket "{ticket.subject}" has been responded to.',
            notification_type="system",
            data={"ticket_id": str(ticket.id)},
        )
        return Response(SupportTicketSerializer(ticket).data)
