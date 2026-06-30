from datetime import timedelta
from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone

from accounts.models import Address
from backend.data import CustomerFlowRepository
from helpers.delivery_quotes import quote_vendor_delivery
from helpers.vendor_hours import is_vendor_open_now
from vendors.data import FulfillmentInventoryRepository, FulfillmentNodeRepository
from vendors.serializers.public import VendorListSerializer


@dataclass
class FulfillmentQuoteOrigin:
    id: str
    store_name: str
    state: str
    city: str
    latitude: Decimal
    longitude: Decimal
    max_delivery_radius_km: Decimal
    instant_delivery_radius_km: Decimal
    base_prep_time_min: int
    delivery_time_per_km_min: Decimal


class CustomerLocationMixin:
    repository = CustomerFlowRepository
    fulfillment_repository = FulfillmentNodeRepository
    fulfillment_inventory_repository = FulfillmentInventoryRepository

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

    def empty_promise_payload(self) -> dict:
        return {
            'fulfillment_node': None,
            'promise': None,
            'availability_summary': {
                'available_product_count': 0,
                'available_store_count': 0,
                'instant_store_count': 0,
            },
        }

    def promise_payload(self, nearest: dict | None, serviceable: list, instant: list) -> dict:
        if not nearest:
            return self.empty_promise_payload()

        eta_minutes = nearest.get('estimated_delivery_minutes')
        promise_expires_at = timezone.now() + timedelta(minutes=5)
        existing_node = nearest.get('fulfillment_node') or {}
        node_id = str(existing_node.get('id') or nearest.get('id') or nearest.get('vendor_id') or '')
        vendor_ids = [item.get('id') or item.get('vendor_id') for item in serviceable]
        node_ids = [
            item.get('fulfillment_node', {}).get('id')
            for item in serviceable
            if item.get('fulfillment_node', {}).get('id')
        ]
        node_product_count = self.fulfillment_inventory_repository.available_product_count_for_nodes(node_ids) if node_ids else 0
        vendor_product_count = self.repository.customer_visible_products().filter(
            vendor_id__in=[vendor_id for vendor_id in vendor_ids if vendor_id]
        ).count()
        available_product_count = node_product_count or vendor_product_count
        fulfillment_node = existing_node or {
            'id': node_id,
            'type': 'vendor_store',
            'name': nearest.get('store_name') or nearest.get('vendor_name') or nearest.get('name') or '',
            'vendor_id': str(nearest.get('vendor_id') or nearest.get('id') or ''),
            'distance_km': nearest.get('distance_km'),
            'is_instant': bool(nearest.get('within_instant_radius')),
            'is_accepting_orders': nearest.get('is_accepting_orders', True),
            'coverage_radius_km': nearest.get('instant_radius_km'),
        }
        promise = {
            'id': f"vendor_store:{node_id}:{eta_minutes or 'unknown'}",
            'fulfillment_node_id': node_id,
            'eta_min_minutes': eta_minutes,
            'eta_max_minutes': eta_minutes,
            'eta_label': nearest.get('estimated_delivery_label') or '',
            'delivery_fee': nearest.get('delivery_fee'),
            'distance_km': nearest.get('distance_km'),
            'vehicle_type': nearest.get('vehicle_type') or '',
            'expires_at': promise_expires_at.isoformat(),
            'requires_confirmation': bool(nearest.get('requires_far_delivery_confirmation')),
            'is_instant': bool(nearest.get('within_instant_radius')),
        }
        return {
            'fulfillment_node': fulfillment_node,
            'promise': promise,
            'availability_summary': {
                'available_product_count': available_product_count,
                'available_store_count': len(serviceable),
                'instant_store_count': len(instant),
                'source': 'fulfillment_node' if existing_node else 'vendor_store_fallback',
            },
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
                **self.empty_promise_payload(),
            }

        serviceable, instant = self.fulfillment_serviceability(request, address)
        if not serviceable and not self.has_configured_fulfillment_nodes_for_address(address):
            serviceable, instant = self.vendor_store_serviceability(request, address)

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
            **self.promise_payload(nearest, serviceable, instant),
        }

    def has_configured_fulfillment_nodes_for_address(self, address) -> bool:
        return bool(self.fulfillment_repository.active_nodes_for_rollout_area(address))

    def vendor_store_serviceability(self, request, address) -> tuple[list, list]:
        serviceable = []
        instant = []
        for store in self.repository.open_approved_stores():
            if not is_vendor_open_now(store):
                continue
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
        return serviceable, instant

    def fulfillment_serviceability(self, request, address) -> tuple[list, list]:
        serviceable = []
        instant = []
        for node in self.fulfillment_repository.active_nodes_for_address(address):
            vendor = node.vendor
            if not self.node_vendor_is_customer_visible(vendor):
                continue
            try:
                quote = quote_vendor_delivery(self.quote_origin_for_node(node), address)
            except Exception:
                continue
            if not quote.is_serviceable:
                continue
            payload = VendorListSerializer(vendor, context={'request': request}).data
            quote_payload = quote.as_dict()
            quote_payload.update({
                'vendor_id': str(vendor.id),
                'vendor_name': vendor.store_name,
                'fulfillment_node_id': str(node.id),
                'fulfillment_node': self.node_payload(node, quote_payload),
            })
            payload.update(quote_payload)
            serviceable.append(payload)
            if quote.within_instant_radius:
                instant.append(payload)
        return serviceable, instant

    def node_vendor_is_customer_visible(self, vendor) -> bool:
        if not vendor:
            return False
        return (
            vendor.status == 'approved'
            and vendor.is_open
            and vendor.is_accepting_orders
            and is_vendor_open_now(vendor)
        )

    def quote_origin_for_node(self, node) -> FulfillmentQuoteOrigin:
        return FulfillmentQuoteOrigin(
            id=str(node.id),
            store_name=node.name,
            state=node.state,
            city=node.city,
            latitude=node.latitude,
            longitude=node.longitude,
            max_delivery_radius_km=node.max_delivery_radius_km,
            instant_delivery_radius_km=node.instant_radius_km,
            base_prep_time_min=node.base_prep_time_min,
            delivery_time_per_km_min=node.delivery_time_per_km_min,
        )

    def node_payload(self, node, quote_payload: dict) -> dict:
        vendor_id = str(node.vendor_id) if node.vendor_id else ''
        return {
            'id': str(node.id),
            'type': node.node_type,
            'name': node.name,
            'vendor_id': vendor_id,
            'distance_km': quote_payload.get('distance_km'),
            'is_instant': bool(quote_payload.get('within_instant_radius')),
            'is_accepting_orders': node.is_accepting_orders,
            'coverage_radius_km': quote_payload.get('instant_radius_km'),
            'city': node.city,
            'state': node.state,
            'postal_code': node.postal_code,
        }
