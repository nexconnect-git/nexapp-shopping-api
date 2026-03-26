from django.utils import timezone
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from accounts.permissions import IsAdminRole, IsApprovedVendor
from .models import SupportTicket
from .serializers import SupportTicketSerializer


class VendorTicketListCreateView(APIView):
    """GET/POST /api/support/tickets/  — vendor creates/lists own tickets"""
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request):
        tickets = SupportTicket.objects.filter(vendor=request.user.vendor_profile)
        return Response(SupportTicketSerializer(tickets, many=True).data)

    def post(self, request):
        serializer = SupportTicketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(vendor=request.user.vendor_profile)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class VendorTicketDetailView(APIView):
    """GET /api/support/tickets/<pk>/  — vendor views a single ticket"""
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request, pk):
        try:
            ticket = SupportTicket.objects.get(pk=pk, vendor=request.user.vendor_profile)
        except SupportTicket.DoesNotExist:
            return Response({'error': 'Ticket not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(SupportTicketSerializer(ticket).data)


class AdminTicketListView(generics.ListAPIView):
    """GET /api/admin/support/tickets/  — admin lists all tickets"""
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = SupportTicketSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        qs = SupportTicket.objects.select_related('vendor').order_by('-created_at')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class AdminTicketRespondView(APIView):
    """PATCH /api/admin/support/tickets/<pk>/respond/  — admin responds to a ticket"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def patch(self, request, pk):
        try:
            ticket = SupportTicket.objects.get(pk=pk)
        except SupportTicket.DoesNotExist:
            return Response({'error': 'Ticket not found.'}, status=status.HTTP_404_NOT_FOUND)

        response_text = request.data.get('admin_response', '').strip()
        new_status = request.data.get('status', 'in_progress')
        if not response_text:
            return Response({'error': 'admin_response is required.'}, status=status.HTTP_400_BAD_REQUEST)

        ticket.admin_response = response_text
        ticket.status = new_status
        ticket.responded_by = request.user
        ticket.responded_at = timezone.now()
        ticket.save()

        # Notify the vendor
        from notifications.models import Notification
        Notification.objects.create(
            user=ticket.vendor.user,
            title='Support Ticket Updated',
            message=f'Your ticket "{ticket.subject}" has been responded to.',
            notification_type='system',
            data={'ticket_id': str(ticket.id)},
        )
        return Response(SupportTicketSerializer(ticket).data)
