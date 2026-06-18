from decimal import Decimal

from accounts.models import Address
from backend.data import CustomerFlowRepository
from helpers.delivery_quotes import quote_vendor_delivery
from vendors.serializers.public import VendorListSerializer


class CustomerLocationMixin:
    repository = CustomerFlowRepository

    def request_address(self, request) -> Address | None:
        lat = request.query_params.get('lat') or request.data.get('lat')
        lng = request.query_params.get('lng') or request.data.get('lng')
        if lat is None or lng is None:
            return None
        try:
            return Address(
                user=request.user if getattr(request.user, 'is_authenticated', False) else None,
                full_name='Customer',
                phone='',
                address_line1=request.query_params.get('label') or request.data.get('label') or 'Selected location',
                city=request.query_params.get('city') or request.data.get('city') or '',
                state=request.query_params.get('state') or request.data.get('state') or '',
                postal_code=request.query_params.get('postal_code') or request.data.get('postal_code') or '',
                latitude=Decimal(str(lat)),
                longitude=Decimal(str(lng)),
            )
        except Exception:
            return None

    def location_payload(self, request, serviceability: dict) -> dict:
        lat = request.query_params.get('lat') or request.data.get('lat')
        lng = request.query_params.get('lng') or request.data.get('lng')
        city = request.query_params.get('city') or request.data.get('city') or ''
        state = request.query_params.get('state') or request.data.get('state') or ''
        postal_code = request.query_params.get('postal_code') or request.data.get('postal_code') or ''
        label = request.query_params.get('label') or request.data.get('label') or city or postal_code or 'Selected location'
        return {
            'serviceable': serviceability['is_serviceable'],
            'label': label,
            'lat': lat,
            'lng': lng,
            'city': city,
            'state': state,
            'postal_code': postal_code,
            'eta_label': serviceability['eta_label'],
        }

    def serviceability_payload(self, request) -> dict:
        address = self.request_address(request)
        if not address:
            return {
                'is_serviceable': False,
                'message': 'Select a delivery location to see instant stores.',
                'nearby_store_count': 0,
                'instant_store_count': 0,
                'eta_label': '',
                'nearest_store_eta': None,
                'nearest_store': None,
            }

        serviceable = []
        instant = []
        for store in self.repository.open_approved_stores():
            try:
                quote = quote_vendor_delivery(store, address)
            except Exception:
                continue
            if not quote.is_serviceable:
                continue
            payload = VendorListSerializer(store, context={'request': request}).data
            payload.update(quote.as_dict())
            serviceable.append(payload)
            if quote.within_instant_radius:
                instant.append(payload)

        serviceable.sort(
            key=lambda item: (
                item.get('estimated_delivery_minutes') or 999999,
                item.get('distance_km') or 999999,
            )
        )
        nearest = serviceable[0] if serviceable else None
        eta_minutes = nearest.get('estimated_delivery_minutes') if nearest else None
        eta_label = nearest.get('estimated_delivery_label') if nearest else ''
        return {
            'is_serviceable': bool(serviceable),
            'message': '' if serviceable else 'We are not delivering to this location yet.',
            'nearby_store_count': len(serviceable),
            'instant_store_count': len(instant),
            'eta_label': eta_label,
            'nearest_store_eta': eta_minutes,
            'nearest_store': nearest,
        }
