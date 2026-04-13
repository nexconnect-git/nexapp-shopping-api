from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from accounts.actions.admin_actions import GetAdminStatsAction


class AdminStatsView(APIView):
    """GET /api/admin/stats/ — fetch platform-wide live statistics for admin dashboard."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        action = GetAdminStatsAction()
        stats = action.execute()
        return Response(stats, status=status.HTTP_200_OK)
