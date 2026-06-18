from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.actions.admin_actions import CheckUserAvailabilityAction
from accounts.permissions import IsAdminRole


class AdminIdentityAvailabilityView(APIView):
    """Admin-only identity availability checks for onboarding forms."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        try:
            result = CheckUserAvailabilityAction().execute(
                field=request.data.get('field', ''),
                value=request.data.get('value', ''),
                exclude_user_id=request.data.get('exclude_user_id', '') or '',
                role=request.data.get('role', '') or '',
            )
            return Response(result)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
