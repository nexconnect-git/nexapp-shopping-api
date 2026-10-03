from vendors.data.base import BaseRepository
from vendors.models.vendor import Vendor
from vendors.models.vendor_wallet import VendorWalletTransaction


class VendorWalletRepository(BaseRepository):
    def __init__(self):
        super().__init__(VendorWalletTransaction)

    @staticmethod
    def lock_vendor(vendor_id):
        return Vendor.objects.select_for_update().get(pk=vendor_id)

    @staticmethod
    def order_credit(vendor, reference_id):
        return VendorWalletTransaction.objects.filter(
            vendor=vendor, reference_id=reference_id, source='order_earning', transaction_type='credit',
        ).first()
