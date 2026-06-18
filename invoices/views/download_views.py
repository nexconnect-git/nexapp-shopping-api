from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from invoices.actions import GetInvoiceDownloadAction


class InvoiceDownloadView(APIView):
    """GET /api/invoices/<pk>/download/."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        invoice, error, response_status = GetInvoiceDownloadAction().execute(request.user, pk)
        if error:
            return Response(error, status=response_status)

        response = HttpResponse(invoice.pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="{invoice.pdf_file.name.split("/")[-1]}"'
        )
        return response
