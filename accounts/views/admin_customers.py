from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from accounts.permissions import IsAdminRole
from accounts.models.user import User
from accounts.models.loyalty import LoyaltyAccount, LoyaltyTransaction
from accounts.serializers.user_serializers import AdminUserSerializer
from accounts.actions.admin_actions import UpdateAccountStatusAction
from accounts.data.user_repository import UserRepository


class AdminCustomerViewSet(viewsets.ModelViewSet):
    """Admin-only resource for managing customers."""
    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
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

    @action(detail=True, methods=['get'], url_path='loyalty')
    def loyalty(self, request, **_kwargs):
        """GET /api/admin/customers/<pk>/loyalty/ — return balance + recent transactions."""
        user = self.get_object()
        account, _ = LoyaltyAccount.objects.get_or_create(user=user)
        transactions = LoyaltyTransaction.objects.filter(account=account).order_by('-created_at')[:20]
        tx_data = [
            {
                'id': str(t.id),
                'points': t.points,
                'transaction_type': t.transaction_type,
                'description': t.description,
                'reference_id': t.reference_id,
                'created_at': t.created_at.isoformat(),
            }
            for t in transactions
        ]
        return Response({
            'points': account.points,
            'lifetime_points': account.lifetime_points,
            'transactions': tx_data,
        })

    @action(detail=True, methods=['post'], url_path='loyalty/adjust')
    def adjust_loyalty(self, request, **_kwargs):
        """POST /api/admin/customers/<pk>/loyalty/adjust/ — credit or debit points."""
        user = self.get_object()
        operation = request.data.get('operation')
        try:
            amount = int(request.data.get('amount', 0))
        except (TypeError, ValueError):
            return Response({'error': 'amount must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)
        reason = str(request.data.get('reason', '')).strip()

        if operation not in ('credit', 'debit'):
            return Response({'error': 'operation must be "credit" or "debit".'}, status=status.HTTP_400_BAD_REQUEST)
        if amount <= 0:
            return Response({'error': 'amount must be positive.'}, status=status.HTTP_400_BAD_REQUEST)
        if not reason:
            return Response({'error': 'reason is required.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            account, _ = LoyaltyAccount.objects.select_for_update().get_or_create(user=user)
            if operation == 'debit' and account.points < amount:
                return Response(
                    {'error': f'Insufficient balance. Customer has {account.points} pts.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            delta = amount if operation == 'credit' else -amount
            account.points += delta
            if operation == 'credit':
                account.lifetime_points += amount
            account.save(update_fields=['points', 'lifetime_points', 'updated_at'])
            LoyaltyTransaction.objects.create(
                account=account,
                points=delta,
                transaction_type='admin_credit' if operation == 'credit' else 'admin_debit',
                reference_id=f'admin_{request.user.id}',
                description=reason,
            )

        return Response({
            'points': account.points,
            'lifetime_points': account.lifetime_points,
            'adjusted': delta,
            'message': f'{operation.capitalize()}ed {amount} pts. New balance: {account.points} pts.',
        })
