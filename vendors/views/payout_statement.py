from django.http import FileResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from accounts.permissions import HasAdminPermission
from vendors.actions import GeneratePayoutStatementAction


class AdminPayoutStatementView(APIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.view'

    def get(self, request, kind, pk):
        document = GeneratePayoutStatementAction().execute(kind, pk)
        return FileResponse(document, as_attachment=True, filename=f'settlement-{pk}.pdf', content_type='application/pdf')
