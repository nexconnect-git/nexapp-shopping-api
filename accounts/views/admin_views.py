from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAdminRole
from accounts.data.user_repository import UserRepository
from accounts.serializers.user_serializers import AdminUserSerializer
from accounts.actions.admin_actions import UpdateAccountStatusAction

class AdminUserViewSet(viewsets.ModelViewSet):
    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        return UserRepository.get_all()

    @action(detail=True, methods=['post'], url_path='status')
    def update_status(self, request, pk=None):
        user = self.get_object()
        new_status = request.data.get("status")
        if not new_status:
            return Response({"error": "status is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            action = UpdateAccountStatusAction()
            updated_user = action.execute(user_id=pk, status=new_status, request=request)
            return Response(self.get_serializer(updated_user).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
