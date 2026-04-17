"""Loyalty points views."""

import decimal

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounts.actions.loyalty_actions import (
    GetOrCreateLoyaltyAction,
    RUPEE_VALUE_PER_POINT,
    MAX_POINTS_REDEMPTION_PCT,
)


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
            'rupee_value': str((account.points * RUPEE_VALUE_PER_POINT).quantize(decimal.Decimal('0.01'))),
            'value_per_point': str(RUPEE_VALUE_PER_POINT),
            'transactions': tx_data,
        })


class LoyaltyPreviewView(APIView):
    """GET /api/auth/loyalty/preview/?order_total=X — preview redeemable points for a cart total."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            order_total = decimal.Decimal(str(request.query_params.get('order_total', '0')))
        except (decimal.InvalidOperation, ValueError):
            return Response({'error': 'Invalid order_total.'}, status=400)

        account = GetOrCreateLoyaltyAction.execute(request.user)
        max_discount = (order_total * MAX_POINTS_REDEMPTION_PCT / 100).quantize(decimal.Decimal('0.01'))
        max_redeemable_points = min(
            account.points,
            int(max_discount / RUPEE_VALUE_PER_POINT),
        )
        discount = (decimal.Decimal(str(max_redeemable_points)) * RUPEE_VALUE_PER_POINT).quantize(decimal.Decimal('0.01'))

        return Response({
            'points': account.points,
            'max_redeemable': max_redeemable_points,
            'discount': str(discount),
            'value_per_point': str(RUPEE_VALUE_PER_POINT),
            'max_pct': MAX_POINTS_REDEMPTION_PCT,
        })
