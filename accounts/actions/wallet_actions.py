"""Wallet business logic actions."""

import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from accounts.data.wallet_repository import WalletRepository, WalletTopUpRepository
from accounts.models.wallet import Wallet
from orders.services.razorpay_service import RazorpayService

logger = logging.getLogger(__name__)


class GetOrCreateWalletAction:
    @staticmethod
    def execute(user) -> Wallet:
        return WalletRepository.get_for_user(user)


class CreditWalletAction:
    @staticmethod
    @transaction.atomic
    def execute(user, amount: Decimal, source: str, reference_id: str = '', description: str = '') -> Wallet:
        amount = _positive_amount(amount)
        wallet = WalletRepository.get_for_user(user, lock=True)
        if reference_id and source in ('topup', 'refund') and WalletRepository.credit_exists(wallet, source, reference_id):
            return wallet
        wallet.balance += amount
        wallet.save(update_fields=['balance', 'updated_at'])
        WalletRepository.record(
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
        amount = _positive_amount(amount)
        wallet = WalletRepository.get_for_user(user, lock=True)
        if wallet.balance < amount:
            raise ValueError(
                f"Insufficient wallet balance. Available: ₹{wallet.balance}, Required: ₹{amount}"
            )
        wallet.balance -= amount
        wallet.save(update_fields=['balance', 'updated_at'])
        WalletRepository.record(
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
        amount = _positive_amount(amount_inr)
        if amount < 1:
            raise ValueError("Minimum top-up amount is ₹1.")
        rz_order = RazorpayService().create_order(
            amount_inr=amount,
            receipt=f"wallet-{user.id.hex[:24]}",
        )
        if rz_order['amount'] != int(amount * 100) or rz_order['currency'] != 'INR':
            raise ValueError('Payment gateway returned an unexpected amount or currency.')
        WalletTopUpRepository().create(
            user=user, gateway_order_id=rz_order['id'], amount=amount, currency='INR',
        )
        return {
            'razorpay_order_id': rz_order['id'],
            'amount': rz_order['amount'],
            'currency': rz_order['currency'],
        }


class VerifyWalletTopUpAction:
    """Verify Razorpay payment signature and credit the wallet."""

    @staticmethod
    @transaction.atomic
    def execute(user, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str, amount_inr=None) -> Wallet:
        topup = WalletTopUpRepository.get_locked(razorpay_order_id, user)
        if not topup:
            raise ValueError('Wallet payment session not found. Please restart the top-up.')
        gateway = RazorpayService()
        if not gateway.verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
            raise ValueError("Payment signature verification failed.")
        if topup.credited_at:
            if topup.gateway_payment_id != razorpay_payment_id:
                raise ValueError('This top-up was already credited using another payment.')
            return WalletRepository.get_for_user(user)
        if WalletTopUpRepository.payment_used(razorpay_payment_id):
            raise ValueError('This payment has already been credited.')
        try:
            payment = gateway.fetch_payment(razorpay_payment_id)
        except Exception as exc:
            logger.exception('Could not fetch wallet payment %s.', razorpay_payment_id)
            raise ValueError('Could not confirm payment. Please try again.') from exc
        if (
            payment.get('order_id') != topup.gateway_order_id
            or payment.get('amount') != int(topup.amount * 100)
            or payment.get('currency') != topup.currency
            or payment.get('status') != 'captured'
        ):
            raise ValueError('Payment amount, currency, order, or capture status does not match this top-up.')
        wallet = CreditWalletAction.execute(
            user=user,
            amount=topup.amount,
            source='topup',
            reference_id=razorpay_payment_id,
            description=f"Wallet top-up via Razorpay ({razorpay_payment_id})",
        )
        topup.gateway_payment_id = razorpay_payment_id
        topup.credited_at = timezone.now()
        topup.save(update_fields=['gateway_payment_id', 'credited_at'])
        return wallet


def _positive_amount(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount <= 0 or amount > Decimal('9999999999.99'):
            raise ValueError('Amount must be a positive, finite number within the supported range.')
        if amount != amount.quantize(Decimal('0.01')):
            raise ValueError('Amount must have at most two decimal places.')
        return amount.quantize(Decimal('0.01'))
    except InvalidOperation as exc:
        raise ValueError('Amount must be a valid number.') from exc
