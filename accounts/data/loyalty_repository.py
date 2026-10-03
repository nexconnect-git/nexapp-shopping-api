from accounts.models.loyalty import LoyaltyAccount, LoyaltyTransaction
from vendors.data.base import BaseRepository


class LoyaltyRepository(BaseRepository):
    def __init__(self):
        super().__init__(LoyaltyAccount)

    @staticmethod
    def get_locked(user):
        return LoyaltyAccount.objects.select_for_update().get_or_create(user=user)[0]

    @staticmethod
    def earned(account, reference_id):
        return LoyaltyTransaction.objects.filter(
            account=account, reference_id=reference_id, transaction_type='earn',
        ).exists()

    @staticmethod
    def record(**kwargs):
        return LoyaltyTransaction.objects.create(**kwargs)
