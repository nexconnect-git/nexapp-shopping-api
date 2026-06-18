from django.core.cache import cache
from rest_framework import status

from api_v1.data import V1AddressRepository, V1CartRepository, V1VendorRepository
from api_v1.helpers import cart_hash, serviceability_for_vendor


DELIVERY_QUOTE_TTL = 300


class CartDeliveryQuoteV1Action:
    def __init__(
        self,
        address_repository: V1AddressRepository = None,
        cart_repository: V1CartRepository = None,
        vendor_repository: V1VendorRepository = None,
    ):
        self.address_repository = address_repository or V1AddressRepository()
        self.cart_repository = cart_repository or V1CartRepository()
        self.vendor_repository = vendor_repository or V1VendorRepository()

    def execute(self, user, address_id):
        if not address_id:
            return None, {'error': 'address_id is required.'}, status.HTTP_400_BAD_REQUEST

        address = self.address_repository.get_for_user(address_id, user)
        if not address:
            return None, {'error': 'Address not found.'}, status.HTTP_404_NOT_FOUND
        if not address.latitude or not address.longitude:
            return None, {'error': 'Address has no coordinates.'}, status.HTTP_422_UNPROCESSABLE_ENTITY

        cart = self.cart_repository.get_for_user(user)
        if not cart:
            return {'vendors': [], 'all_serviceable': True}, None, status.HTTP_200_OK

        cache_key = f'v1:quote:{user.id}:{cart_hash(cart)}:{address_id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached, None, status.HTTP_200_OK

        vendor_ids = {
            item.product.vendor_id
            for item in cart.items.all()
            if getattr(item.product, 'vendor_id', None)
        }
        vendors = self.vendor_repository.get_approved_by_ids(vendor_ids)
        customer_lat = float(address.latitude)
        customer_lon = float(address.longitude)

        vendor_quotes = []
        all_serviceable = True
        for vendor in vendors:
            serviceability = serviceability_for_vendor(vendor, customer_lat, customer_lon)
            if not serviceability.is_serviceable:
                all_serviceable = False
            vendor_quotes.append({
                'vendor_id': str(vendor.id),
                'store_name': vendor.store_name,
                'delivery_type': serviceability.delivery_type,
                'distance_km': serviceability.distance_km,
                'eta_min': serviceability.eta_min,
                'is_serviceable': serviceability.is_serviceable,
            })

        result = {'vendors': vendor_quotes, 'all_serviceable': all_serviceable}
        cache.set(cache_key, result, DELIVERY_QUOTE_TTL)
        return result, None, status.HTTP_200_OK
