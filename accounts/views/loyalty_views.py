"""Loyalty points views."""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounts.actions.loyalty_actions import GetOrCreateLoyaltyAction, RUPEE_VALUE_PER_POINT


class LoyaltyView(APIView):
    """GET /api/auth/loyalty/ — return points balance and recent transactions."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        account = GetOrCreateLoyaltyAction.execute(request.user)
        transactions = account.transactions.all()[:50]
        tx_data = [
            {
                'id': str(tx.id),
                'points': tx.points,
                'transaction_type': tx.transaction_type,
                'reference_id': tx.reference_id,
                'description': tx.description,
                'created_at': tx.created_at.isoformat(),
            }
            for tx in transactions
        ]
        return Response({
            'points': account.points,
            'lifetime_points': account.lifetime_points,
            'rupee_value': str((account.points * RUPEE_VALUE_PER_POINT).quantize(__import__('decimal').Decimal('0.01'))),
            'value_per_point': str(RUPEE_VALUE_PER_POINT),
            'transactions': tx_data,
        })
