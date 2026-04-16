"""Wallet business logic actions."""

import logging
from decimal import Decimal

from django.db import transaction

from accounts.models.wallet import Wallet, WalletTransaction
from orders.services.razorpay_service import RazorpayService

logger = logging.getLogger(__name__)


class GetOrCreateWalletAction:
    @staticmethod
    def execute(user) -> Wallet:
        wallet, _ = Wallet.objects.get_or_create(user=user)
        return wallet


class CreditWalletAction:
    @staticmethod
    @transaction.atomic
    def execute(user, amount: Decimal, source: str, reference_id: str = '', description: str = '') -> Wallet:
        wallet = Wallet.objects.select_for_update().get_or_create(user=user)[0]
        wallet.balance += amount
        wallet.save(update_fields=['balance', 'updated_at'])
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=amount,
            transaction_type='credit',
            source=source,
            reference_id=reference_id,
            description=description or f"Credit via {source}",
        )
        return wallet


class DebitWalletAction:
    @staticmethod
    @transaction.atomic
    def execute(user, amount: Decimal, source: str, reference_id: str = '', description: str = '') -> Wallet:
        wallet = Wallet.objects.select_for_update().get_or_create(user=user)[0]
        if wallet.balance < amount:
            raise ValueError(
                f"Insufficient wallet balance. Available: ₹{wallet.balance}, Required: ₹{amount}"
            )
        wallet.balance -= amount
        wallet.save(update_fields=['balance', 'updated_at'])
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=amount,
            transaction_type='debit',
            source=source,
            reference_id=reference_id,
            description=description or f"Debit via {source}",
        )
        return wallet


class InitiateWalletTopUpAction:
    """Create a Razorpay order to top-up the wallet."""

    @staticmethod
    def execute(user, amount_inr: float) -> dict:
        if amount_inr < 1:
            raise ValueError("Minimum top-up amount is ₹1.")
        rz_order = RazorpayService().create_order(
            amount_inr=amount_inr,
            receipt=f"wallet-topup-{user.id}",
        )
        return {
            'razorpay_order_id': rz_order['id'],
            'amount': rz_order['amount'],
            'currency': rz_order['currency'],
        }


class VerifyWalletTopUpAction:
    """Verify Razorpay payment signature and credit the wallet."""

    @staticmethod
    def execute(user, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str, amount_inr: float) -> Wallet:
        if not RazorpayService().verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
            raise ValueError("Payment signature verification failed.")

        # Idempotency: skip if this payment was already credited
        if WalletTransaction.objects.filter(reference_id=razorpay_payment_id).exists():
            wallet, _ = Wallet.objects.get_or_create(user=user)
            return wallet

        return CreditWalletAction.execute(
            user=user,
            amount=Decimal(str(amount_inr)),
            source='topup',
            reference_id=razorpay_payment_id,
            description=f"Wallet top-up via Razorpay ({razorpay_payment_id})",
        )
