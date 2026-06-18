from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from invoices.actions import GenerateInvoiceAction
from invoices.serializers import InvoiceSerializer


class InvoiceGenerateView(APIView):
    """POST /api/invoices/generate/."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        invoice, error, response_status = GenerateInvoiceAction().execute(
            user=request.user,
            payload=request.data,
        )
        if error:
            return Response(error, status=response_status)
        return Response(InvoiceSerializer(invoice).data, status=response_status)
