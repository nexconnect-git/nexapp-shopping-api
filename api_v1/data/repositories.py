from accounts.models.address import Address
from orders.models import Cart
from vendors.data import VendorRepository
from vendors.models import Vendor


class V1AddressRepository:
    @staticmethod
    def get_for_user(address_id, user):
        try:
            return Address.objects.get(pk=address_id, user=user)
        except Address.DoesNotExist:
            return None


class V1CartRepository:
    @staticmethod
    def get_for_user(user):
        try:
            return Cart.objects.prefetch_related('items__product__vendor').get(user=user)
        except Cart.DoesNotExist:
            return None


class V1VendorRepository:
    def __init__(self, vendor_repository: VendorRepository = None):
        self.vendor_repository = vendor_repository or VendorRepository()

    def get_approved(self, category=None):
        return self.vendor_repository.get_approved_vendors(category=category)

    @staticmethod
    def get_approved_by_id(vendor_id):
        try:
            return Vendor.objects.get(pk=vendor_id, status='approved')
        except Vendor.DoesNotExist:
            return None

    @staticmethod
    def get_approved_by_ids(vendor_ids):
        return Vendor.objects.filter(pk__in=vendor_ids, status='approved')
