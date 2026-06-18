from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from invoices.data import InvoiceRepository
from invoices.serializers import InvoiceSerializer


class UserInvoiceListView(generics.ListAPIView):
    """GET /api/invoices/."""

    permission_classes = [IsAuthenticated]
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        return InvoiceRepository.get_for_user(self.request.user)
