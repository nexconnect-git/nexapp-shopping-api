from django.core.cache import cache
from rest_framework import status

from api_v1.data import V1VendorRepository
from api_v1.helpers import serviceability_for_vendor
from api_v1.serializers import VendorV1Serializer
from delivery.services.distance import NOT_SERVICEABLE


NEARBY_VENDORS_TTL = 120


class NearbyVendorsV1Action:
    def __init__(self, repository: V1VendorRepository = None):
        self.repository = repository or V1VendorRepository()

    def execute(self, lat: float, lng: float, category=None):
        cache_key = f"v1:nearby:{round(lat, 1)}:{round(lng, 1)}:{category or 'all'}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        results = []
        for vendor in self.repository.get_approved(category=category):
            serviceability = serviceability_for_vendor(vendor, lat, lng)
            if serviceability.delivery_type == NOT_SERVICEABLE:
                continue
            data = VendorV1Serializer(vendor).data
            data['distance_km'] = serviceability.distance_km
            data['eta_min'] = serviceability.eta_min
            data['delivery_type'] = serviceability.delivery_type
            results.append(data)

        results.sort(key=lambda item: item['distance_km'])
        cache.set(cache_key, results, NEARBY_VENDORS_TTL)
        return results


class VendorServiceabilityV1Action:
    def __init__(self, repository: V1VendorRepository = None):
        self.repository = repository or V1VendorRepository()

    def execute(self, vendor_id, lat: float, lng: float):
        vendor = self.repository.get_approved_by_id(vendor_id)
        if not vendor:
            return None, {'error': 'Vendor not found.'}, status.HTTP_404_NOT_FOUND

        serviceability = serviceability_for_vendor(vendor, lat, lng)
        return {
            'vendor_id': str(vendor.id),
            'delivery_type': serviceability.delivery_type,
            'distance_km': serviceability.distance_km,
            'eta_min': serviceability.eta_min,
            'is_serviceable': serviceability.is_serviceable,
        }, None, status.HTTP_200_OK
