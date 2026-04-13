from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAdminRole
from accounts.models.user import User
from accounts.serializers.user_serializers import AdminUserSerializer
from accounts.actions.admin_actions import UpdateAccountStatusAction
from accounts.data.user_repository import UserRepository

class AdminCustomerViewSet(viewsets.ModelViewSet):
    """Admin-only resource for managing customers."""
    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        # We exclusively return accounts with role 'customer'
        qs = UserRepository.get_customers()
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(email__icontains=search) | qs.filter(full_name__icontains=search)
        return qs

    @action(detail=True, methods=['post'], url_path='status')
    def update_status(self, request, pk=None):
        user = self.get_object()
        new_status = request.data.get("status")
        if not new_status:
            return Response({"error": "status is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            action_obj = UpdateAccountStatusAction()
            updated_user = action_obj.execute(user_id=pk, status=new_status, request=request)
            return Response(self.get_serializer(updated_user).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
