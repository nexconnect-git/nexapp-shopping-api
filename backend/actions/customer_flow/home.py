from accounts.models import Address
from backend.actions.customer_flow.fulfillment_filters import filter_products_for_fulfillment_node
from backend.actions.customer_flow.location import CustomerLocationMixin
from backend.actions.customer_flow.orders import GetCustomerActiveOrderAction
from backend.actions.customer_flow.personalization import GetCustomerBuyAgainAction
from backend.data import CustomerFlowRepository
from helpers.delivery_quotes import quote_vendor_delivery
from helpers.vendor_hours import is_vendor_open_now
from products.data.category_repository import CategoryRepository
from products.serializers import CategorySerializer, ProductListSerializer
from vendors.serializers.public import VendorListSerializer
from orders.serializers.coupon_serializers import CouponSerializer


class GetCustomerFlowHomeAction(CustomerLocationMixin):
    repository = CustomerFlowRepository

    def execute(self, request) -> dict:
        address = self.request_address(request)
        serviceability = self.serviceability_payload(request)
        fulfillment_node_payload = serviceability.get('fulfillment_node') or {}
        fulfillment_node_id = fulfillment_node_payload.get('id')
        fulfillment_node_type = fulfillment_node_payload.get('type')
        inventory_node_id = fulfillment_node_id if fulfillment_node_type != 'vendor_store' else None
        fulfillment_vendor_id = fulfillment_node_payload.get('vendor_id')
        is_serviceable = serviceability.get('is_serviceable')
        category_ids = CategoryRepository.get_available_customer_category_ids(
            address=address,
            fulfillment_node=fulfillment_node_id,
        )
        categories = CategoryRepository.get_customer_visible(category_ids=category_ids)
        recommendation_snapshot = self.repository.recommendation_snapshot(request.user)
        stores = self._snapshot_ranked_stores(
            recommendation_snapshot,
            self._nearby_stores(request, address),
        )
        if fulfillment_node_id:
            stores = [
                store for store in stores
                if fulfillment_vendor_id and str(store.get('id')) == str(fulfillment_vendor_id)
            ]
        store_ids = [store.get('id') for store in stores]
        products = self._products(store_ids=store_ids, fulfillment_node_id=inventory_node_id)
        if not serviceability.get('is_serviceable'):
            products = products.none()
            categories = categories.none()
        coupons = self.repository.active_coupons()[:6] if is_serviceable else []
        active_order = GetCustomerActiveOrderAction().execute(request)['active_order']
        category_cards = CategorySerializer(categories[:12], many=True, context={'request': request}).data
        buy_again = GetCustomerBuyAgainAction().execute(request)['results']
        if not is_serviceable:
            buy_again = []
        nearby_stores = stores[:12]
        recommended_queryset = self._snapshot_ranked_products(
            snapshot_ids=(recommendation_snapshot.recommended_product_ids if recommendation_snapshot else []),
            products=products,
            fallback_queryset=products,
            limit=16,
        )
        flash_queryset = products.filter(compare_price__gt=0)
        flash_queryset = self._snapshot_ranked_products(
            snapshot_ids=(recommendation_snapshot.flash_deal_product_ids if recommendation_snapshot else []),
            products=products,
            fallback_queryset=flash_queryset,
            limit=12,
        )
        flash_deals = ProductListSerializer(flash_queryset, many=True, context={'request': request}).data
        recommended_products = ProductListSerializer(recommended_queryset, many=True, context={'request': request}).data
        coupon_cards = CouponSerializer(coupons, many=True).data
        hero = self._hero_payload(serviceability, nearby_stores, recommended_products, coupon_cards)

        return {
            'location': self.location_payload(request, serviceability),
            'serviceability': serviceability,
            'active_order': active_order,
            'categories': category_cards,
            'buy_again': buy_again,
            'nearby_stores': nearby_stores,
            'flash_deals': flash_deals,
            'recommended_products': recommended_products,
            'banners': [],
            'coupons': coupon_cards,
            'hero': hero,
            'recommendations_generated_at': (
                recommendation_snapshot.generated_at.isoformat()
                if recommendation_snapshot else None
            ),
            'sections': [
                self._section('categories', 'Shop by category', category_cards, 'category_grid'),
                self._section('nearby_stores', 'Stores near you', nearby_stores, 'store_rail'),
                self._section('flash_deals', 'Flash deals', flash_deals, 'product_rail'),
                self._section('recommended_products', 'Recommended for you', recommended_products, 'product_grid'),
                self._section('buy_again', 'Buy again', buy_again, 'product_rail'),
                self._section('coupons', 'Offers for you', coupon_cards, 'coupon_rail'),
            ],
        }

    def _hero_payload(self, serviceability: dict, stores: list[dict], products: list[dict], coupons: list[dict]) -> dict:
        nearest_store = serviceability.get('nearest_store') or (stores[0] if stores else None)
        featured_product = products[0] if products else None
        best_coupon = coupons[0] if coupons else None
        eta_label = serviceability.get('eta_label') or (nearest_store or {}).get('estimated_delivery_label') or 'Fast delivery'
        return {
            'title': 'Groceries delivered in minutes',
            'subtitle': 'Fresh picks, daily essentials, and local store deals near you.',
            'badge': eta_label,
            'cta_label': 'Shop now',
            'cta_url': '/explore',
            'image': (featured_product or {}).get('image') or (nearest_store or {}).get('banner') or (nearest_store or {}).get('logo') or '',
            'store': nearest_store,
            'coupon': best_coupon,
        }

    def _section(self, key: str, title: str, items: list, layout: str) -> dict:
        return {'key': key, 'title': title, 'layout': layout, 'items': items, 'count': len(items)}

    def _nearby_stores(self, request, address: Address | None) -> list[dict]:
        cards = []
        for store in self.repository.open_approved_stores():
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
        return sorted(
            cards,
            key=lambda item: (
                item.get('distance_km') if item.get('distance_km') is not None else 999999,
                item.get('store_name', '').lower(),
            ),
        )

    def _products(self, store_ids: list[str], fulfillment_node_id=None):
        products = self.repository.customer_visible_products()
        if fulfillment_node_id:
            products = filter_products_for_fulfillment_node(products, fulfillment_node_id)
        if store_ids:
            products = products.filter(vendor_id__in=store_ids)
        return products

    def _snapshot_ranked_products(self, snapshot_ids: list, products, fallback_queryset, limit: int):
        ranked_ids = [str(product_id) for product_id in (snapshot_ids or []) if product_id]
        if not ranked_ids:
            return fallback_queryset[:limit]

        candidate_queryset = fallback_queryset if fallback_queryset is not products else products
        allowed_products = {
            str(product.id): product
            for product in candidate_queryset.filter(id__in=ranked_ids)
        }
        ranked_products = [
            allowed_products[product_id]
            for product_id in ranked_ids
            if product_id in allowed_products
        ][:limit]
        if len(ranked_products) >= limit:
            return ranked_products

        used_ids = {str(product.id) for product in ranked_products}
        for product in fallback_queryset.exclude(id__in=used_ids)[:limit - len(ranked_products)]:
            ranked_products.append(product)
        return ranked_products

    def _snapshot_ranked_stores(self, snapshot, stores: list[dict]) -> list[dict]:
        if not stores:
            return stores
        ranked_ids = [
            str(store_id)
            for store_id in (getattr(snapshot, 'recommended_store_ids', []) or [])
            if store_id
        ]
        if not ranked_ids:
            return stores

        allowed_stores = {
            str(store.get('id')): store
            for store in stores
            if store.get('id')
        }
        ranked_stores = [
            allowed_stores[store_id]
            for store_id in ranked_ids
            if store_id in allowed_stores
        ]
        used_ids = {str(store.get('id')) for store in ranked_stores}
        ranked_stores.extend([
            store
            for store in stores
            if str(store.get('id')) not in used_ids
        ])
        return ranked_stores
