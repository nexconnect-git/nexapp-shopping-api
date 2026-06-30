from decimal import Decimal

from django.db import models
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination

from accounts.models import Address
from helpers.delivery_quotes import quote_vendor_delivery
from products.data.product_repository import ProductRepository
from products.models import Product
from vendors.serializers.public import VendorListSerializer


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def build_request_address(request) -> Address | None:
    lat = request.query_params.get('lat')
    lng = request.query_params.get('lng')
    if lat is None or lng is None:
        return None
    try:
        return Address(
            user=request.user if getattr(request.user, 'is_authenticated', False) else None,
            full_name='Customer',
            phone='',
            address_line1='Selected location',
            city=request.query_params.get('city', ''),
            state=request.query_params.get('state', ''),
            postal_code=request.query_params.get('postal_code', ''),
            latitude=Decimal(str(lat)),
            longitude=Decimal(str(lng)),
        )
    except Exception:
        return None


def matching_product_names(vendor, product_query: str, fulfillment_node=None) -> list[str]:
    if not product_query:
        return []
    search_query = Q()
    for term in [part.strip() for part in product_query.split(',') if part.strip()]:
        search_query |= (
            Q(name__icontains=term)
            | Q(search_keywords__icontains=term)
            | Q(description__icontains=term)
            | Q(brand__icontains=term)
            | Q(category__name__icontains=term)
        )
    if not search_query:
        return []
    products = Product.objects.filter(
        vendor=vendor,
        **ProductRepository.customer_visible_filter(),
        category__is_active=True,
        category__show_in_customer_ui=True,
    ).filter(search_query)
    if fulfillment_node:
        products = products.filter(
            fulfillment_inventory__node=fulfillment_node,
            fulfillment_inventory__is_available=True,
            fulfillment_inventory__stock__gt=0,
            fulfillment_inventory__reserved_stock__lt=models.F("fulfillment_inventory__stock"),
        )
    return list(products.values_list('name', flat=True).distinct()[:3])


def serialize_vendor_cards(
    request,
    vendors,
    address: Address | None,
    product_query='',
    previous_vendor_ids=None,
    fulfillment_node=None,
) -> list[dict]:
    cards = []
    previous_vendor_ids = previous_vendor_ids or set()
    for vendor in vendors:
        payload = VendorListSerializer(vendor, context={'request': request}).data
        payload['matched_products_preview'] = matching_product_names(vendor, product_query, fulfillment_node)

        if address:
            quote = quote_vendor_delivery(vendor, address)
            payload.update(quote.as_dict())
        else:
            payload.setdefault('distance_km', None)
            payload.setdefault('estimated_delivery_minutes', None)
            payload.setdefault('estimated_delivery_label', '')
            payload.setdefault('far_order_eta_label', '')
            payload.setdefault('vehicle_type', '')
            payload.setdefault('vehicle_reason', '')
            payload.setdefault('is_far_delivery', False)
            payload.setdefault('requires_far_delivery_confirmation', False)
            payload.setdefault('within_instant_radius', False)
            payload.setdefault('same_state', False)
            payload.setdefault('is_serviceable', True)
            payload.setdefault('serviceability_error', '')
            payload.setdefault('max_supported_distance_km', 0)
            payload.setdefault('instant_radius_km', 0)

        payload['has_previously_ordered'] = (
            vendor.id in previous_vendor_ids
            or bool(getattr(vendor, 'has_previously_ordered', False))
        )
        cards.append(payload)
    return sort_vendor_cards(cards, 'relevance')


def sort_vendor_cards(cards: list[dict], sort_key: str) -> list[dict]:
    if sort_key == 'rating':
        return sorted(
            cards,
            key=lambda item: (
                -float(item.get('average_rating') or 0),
                item.get('distance_km') if item.get('distance_km') is not None else 999999,
                item.get('store_name', '').lower(),
            ),
        )
    if sort_key == 'distance':
        return sorted(
            cards,
            key=lambda item: (
                item.get('distance_km') if item.get('distance_km') is not None else 999999,
                item.get('store_name', '').lower(),
            ),
        )
    if sort_key == 'min_order_asc':
        return sorted(
            cards,
            key=lambda item: (
                float(item.get('min_order_amount') or 0),
                item.get('distance_km') if item.get('distance_km') is not None else 999999,
                item.get('store_name', '').lower(),
            ),
        )
    return sorted(
        cards,
        key=lambda item: (
            0 if item.get('has_previously_ordered') else 1,
            item.get('distance_km') if item.get('distance_km') is not None else 999999,
            item.get('store_name', '').lower(),
        ),
    )
