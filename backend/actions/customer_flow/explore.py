from django.db.models import Q

from backend.actions.customer_flow.home import GetCustomerFlowHomeAction
from backend.actions.customer_flow.location import CustomerLocationMixin
from backend.actions.customer_flow.query_helpers import (
    category_list_query,
    category_product_query,
    category_store_query,
    truthy_query_param,
)
from backend.data import CustomerFlowRepository
from helpers.delivery_quotes import quote_vendor_delivery
from orders.serializers.coupon_serializers import CouponSerializer
from products.data.category_repository import CategoryRepository
from products.serializers import CategorySerializer, ProductListSerializer
from vendors.serializers.public import VendorListSerializer


class GetCustomerExploreAction(CustomerLocationMixin):
    repository = CustomerFlowRepository

    def execute(self, request) -> dict:
        address = self.request_address(request)
        query = (request.query_params.get('q') or request.query_params.get('search') or '').strip()
        category = (request.query_params.get('category') or '').strip()
        products = self._product_queryset(query=query, category=category)
        stores = self._store_results(request, address, query=query, category=category)
        categories = self._category_queryset(query=query, category=category)
        offers = self.repository.active_coupons()[:8]
        products = self._apply_filters(products, request)

        return {
            'query': query,
            'categories': CategorySerializer(categories[:12], many=True, context={'request': request}).data,
            'products': ProductListSerializer(products[:24], many=True, context={'request': request}).data,
            'stores': stores[:12],
            'offers': CouponSerializer(offers, many=True).data,
            'suggestions': self._suggestions(query, categories),
            'filters': {
                'available': ['instant_only', 'in_stock', 'offers', 'rating', 'delivery_time', 'store', 'category'],
                'active': {key: request.query_params.get(key) for key in request.query_params.keys()},
            },
            'summary': {
                'product_count': products.count(),
                'store_count': len(stores),
                'category_count': categories.count(),
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
        return sorted(cards, key=lambda item: item.get('estimated_delivery_minutes') or 999999)

    def _apply_filters(self, products, request):
        if truthy_query_param(request.query_params.get('in_stock')):
            products = products.filter(stock__gt=0)
        if truthy_query_param(request.query_params.get('offers')):
            products = products.filter(compare_price__gt=0)
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        rating = request.query_params.get('rating')
        if min_price:
            products = products.filter(price__gte=min_price)
        if max_price:
            products = products.filter(price__lte=max_price)
        if rating:
            products = products.filter(average_rating__gte=rating)
        sort = request.query_params.get('sort')
        if sort == 'price_low_high':
            return products.order_by('price', 'name')
        if sort == 'rating':
            return products.order_by('-average_rating', '-total_orders')
        if sort == 'offers':
            return products.order_by('-compare_price', 'price')
        return products

    def _suggestions(self, query: str, categories) -> list[str]:
        if query:
            return [query, f'{query} near me', f'best {query}', f'{query} offers']
        return list(categories.values_list('name', flat=True)[:6])
