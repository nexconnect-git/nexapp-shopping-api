from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsApprovedVendor
from support.actions import CreateTicketAction
from support.data import SupportTicketRepository
from support.serializers import SupportTicketSerializer
from vendors.data.feedback_repository import VendorFeedbackRepository
from vendors.helpers.public_vendor_helpers import StandardPagination


class VendorTicketListCreateView(APIView):
    """GET/POST /api/support/tickets/."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request):
        tickets = VendorFeedbackRepository().tickets(request.user.vendor_profile, request.query_params)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(tickets, request)
        return paginator.get_paginated_response(SupportTicketSerializer(page, many=True).data)

    def post(self, request):
        serializer = SupportTicketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = CreateTicketAction().execute(
            vendor=request.user.vendor_profile,
            validated_data=serializer.validated_data,
        )
        return Response(SupportTicketSerializer(ticket).data, status=status.HTTP_201_CREATED)


class VendorTicketDetailView(APIView):
    """GET /api/support/tickets/<pk>/."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request, pk):
        ticket = SupportTicketRepository.get_by_id_and_vendor(pk, request.user.vendor_profile)
        if not ticket:
            return Response({'error': 'Ticket not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(SupportTicketSerializer(ticket).data)
