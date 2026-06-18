from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from support.actions import AdminRespondToTicketAction
from support.data import SupportTicketRepository
from support.serializers import SupportTicketSerializer


class AdminTicketListView(generics.ListAPIView):
    """GET /api/admin/support/tickets/."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = SupportTicketSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        status_filter = self.request.query_params.get('status')
        if status_filter:
            return SupportTicketRepository.filter_all_by_status(status_filter)
        return SupportTicketRepository.get_all()


class AdminTicketRespondView(APIView):
    """PATCH /api/admin/support/tickets/<pk>/respond/."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def patch(self, request, pk):
        ticket = SupportTicketRepository.get_by_id(pk)
        if not ticket:
            return Response({'error': 'Ticket not found.'}, status=status.HTTP_404_NOT_FOUND)

        response_text = request.data.get('admin_response', '').strip()
        new_status = request.data.get('status', 'in_progress')
        if not response_text:
            return Response(
                {'error': 'admin_response is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ticket = AdminRespondToTicketAction().execute(
            ticket=ticket,
            admin_user=request.user,
            response_text=response_text,
            new_status=new_status,
        )
        return Response(SupportTicketSerializer(ticket).data)
