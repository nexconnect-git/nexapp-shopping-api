from decimal import Decimal, InvalidOperation

from django.db.models import Q

from backend.actions.customer_flow.fulfillment_filters import active_fulfillment_node_for_request, filter_products_for_fulfillment_node
from backend.actions.customer_flow.location import CustomerLocationMixin
from backend.actions.customer_flow.query_helpers import (
    category_list_query,
    category_product_query,
    category_store_query,
)
from backend.data import CustomerFlowRepository
from helpers.delivery_quotes import quote_vendor_delivery
from helpers.vendor_hours import is_vendor_open_now
from orders.serializers.coupon_serializers import CouponSerializer
from products.data.category_repository import CategoryRepository
from products.serializers import CategorySerializer, ProductListSerializer
from vendors.serializers.public import VendorListSerializer


class GetCustomerExploreAction(CustomerLocationMixin):
    repository = CustomerFlowRepository

    def execute(self, request) -> dict:
        address = self.request_address(request)
        serviceability = self.serviceability_payload(request)
        query = (request.query_params.get('q') or request.query_params.get('search') or '').strip()
        category = (request.query_params.get('category') or '').strip()
        products = self._product_queryset(query=query, category=category)
        stores = self._store_results(request, address, query=query, category=category)
        node = active_fulfillment_node_for_request(request)
        if node:
            products = filter_products_for_fulfillment_node(products, node)
            if node.node_type == 'vendor_store':
                stores = [store for store in stores if str(store.get('id')) == str(node.vendor_id)]
        categories = self._category_queryset(query=query, category=category)
        if not serviceability.get('is_serviceable'):
            stores = []
            products = products.none()
            categories = categories.none()
        elif address:
            store_ids = [store.get('id') for store in stores if store.get('id')]
            if store_ids:
                products = self.repository.products_for_vendors(products, store_ids)
            else:
                products = products.none()
                categories = categories.none()
        offers = self.repository.active_coupons()[:8] if serviceability.get('is_serviceable') else []
        products = self._apply_filters(products, request)
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        product_count = products.count()
        category_count = categories.count()
        product_start = (page - 1) * 24
        other_start = (page - 1) * 12
        has_more = (
            product_count > product_start + 24
            or len(stores) > other_start + 12
            or category_count > other_start + 12
        )

        return {
            'query': query,
            'serviceability': serviceability,
            'categories': CategorySerializer(categories[other_start:other_start + 12], many=True, context={'request': request}).data,
            'products': ProductListSerializer(products[product_start:product_start + 24], many=True, context={'request': request}).data,
            'stores': stores[other_start:other_start + 12],
            'page': page,
            'next_page': page + 1 if has_more else None,
            'offers': CouponSerializer(offers, many=True).data,
            'suggestions': self._suggestions(query, categories),
            'filters': {
                'available': ['instant_only', 'in_stock', 'offers', 'rating', 'delivery_time', 'store', 'category'],
                'active': {key: request.query_params.get(key) for key in request.query_params.keys()},
            },
            'summary': {
                'product_count': product_count,
                'store_count': len(stores),
                'category_count': category_count,
            },
        }

    def _product_queryset(self, query: str, category: str):
        return self.repository.searchable_products(
            query=query,
            category_query=category_product_query(category),
        )

    def _category_queryset(self, query: str, category: str):
        categories = CategoryRepository.get_customer_visible()
        if query:
            categories = categories.filter(Q(name__icontains=query) | Q(slug__icontains=query))
        category_query = category_list_query(category)
        if category_query is not None:
            categories = categories.filter(category_query)
        return categories

    def _store_results(self, request, address, query: str, category: str) -> list[dict]:
        stores = self.repository.searchable_stores(
            query=query,
            category_query=category_store_query(category),
        )
        cards = []
        for store in stores:
            if not is_vendor_open_now(store):
                continue
            payload = VendorListSerializer(store, context={'request': request}).data
            if address:
                try:
                    quote = quote_vendor_delivery(store, address)
                except Exception:
                    continue
                if not quote.is_serviceable:
                    continue
                payload.update(quote.as_dict())
            cards.append(payload)
        limit = request.query_params.get('delivery_time')
        if limit:
            try:
                minutes = Decimal(limit)
                if minutes.is_finite() and minutes > 0:
                    cards = [card for card in cards if card.get('estimated_delivery_minutes') is not None and Decimal(str(card['estimated_delivery_minutes'])) <= minutes]
            except (InvalidOperation, TypeError, ValueError):
                cards = []
        return sorted(cards, key=lambda item: item.get('estimated_delivery_minutes') or 999999)

    def _apply_filters(self, products, request):
        return self.repository.filtered_search_products(products, request.query_params)

    def _suggestions(self, query: str, categories) -> list[str]:
        if query:
            return [query, f'{query} near me', f'best {query}', f'{query} offers']
        return list(categories.values_list('name', flat=True)[:6])
