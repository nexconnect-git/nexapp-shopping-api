"""Wallet views — balance, top-up initiation, and top-up verification."""

from decimal import Decimal

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounts.actions.wallet_actions import (
    GetOrCreateWalletAction,
    InitiateWalletTopUpAction,
    VerifyWalletTopUpAction,
)
from accounts.models.wallet import WalletTransaction


class WalletView(APIView):
    """GET /api/auth/wallet/ — return wallet balance and recent transactions."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallet = GetOrCreateWalletAction.execute(request.user)
        transactions = wallet.transactions.all()[:50]
        tx_data = [
            {
                'id': str(tx.id),
                'amount': str(tx.amount),
                'transaction_type': tx.transaction_type,
                'source': tx.source,
                'reference_id': tx.reference_id,
                'description': tx.description,
                'created_at': tx.created_at.isoformat(),
            }
            for tx in transactions
        ]
        return Response({
            'balance': str(wallet.balance),
            'transactions': tx_data,
        })


class InitiateWalletTopUpView(APIView):
    """POST /api/auth/wallet/topup/ — create a Razorpay order for wallet top-up."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        amount = request.data.get('amount')
        if amount is None:
            return Response({'amount': 'This field is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            amount_float = float(amount)
        except (TypeError, ValueError):
            return Response({'amount': 'Must be a valid number.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = InitiateWalletTopUpAction.execute(request.user, amount_inr=amount_float)
            return Response(result, status=status.HTTP_201_CREATED)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class VerifyWalletTopUpView(APIView):
    """POST /api/auth/wallet/verify-topup/ — verify Razorpay signature and credit wallet."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        required = ['razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature', 'amount']
        missing = [f for f in required if not request.data.get(f)]
        if missing:
            return Response(
                {f: 'This field is required.' for f in missing},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            amount_float = float(request.data['amount'])
        except (TypeError, ValueError):
            return Response({'amount': 'Must be a valid number.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            wallet = VerifyWalletTopUpAction.execute(
                user=request.user,
                razorpay_order_id=request.data['razorpay_order_id'],
                razorpay_payment_id=request.data['razorpay_payment_id'],
                razorpay_signature=request.data['razorpay_signature'],
                amount_inr=amount_float,
            )
            return Response({'balance': str(wallet.balance)})
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
