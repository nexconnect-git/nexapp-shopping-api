from accounts.models.wallet import Wallet, WalletTransaction
from accounts.models.wallet_topup import WalletTopUp
from vendors.data.base import BaseRepository


class WalletRepository(BaseRepository):
    def __init__(self):
        super().__init__(Wallet)

    @staticmethod
    def get_for_user(user, lock=False):
        queryset = Wallet.objects.select_for_update() if lock else Wallet.objects
        return queryset.get_or_create(user=user)[0]

    @staticmethod
    def credit_exists(wallet, source, reference_id):
        return WalletTransaction.objects.filter(
            wallet=wallet, source=source, reference_id=reference_id, transaction_type='credit',
        ).exists()

    @staticmethod
    def record(**kwargs):
        return WalletTransaction.objects.create(**kwargs)


class WalletTopUpRepository(BaseRepository):
    def __init__(self):
        super().__init__(WalletTopUp)

    @staticmethod
    def get_locked(order_id, user):
        return WalletTopUp.objects.select_for_update().filter(
            gateway_order_id=order_id, user=user,
        ).first()

    @staticmethod
    def payment_used(payment_id):
        return WalletTopUp.objects.filter(gateway_payment_id=payment_id).exists()
