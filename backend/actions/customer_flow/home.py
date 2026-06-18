from accounts.models import Address
from backend.actions.customer_flow.location import CustomerLocationMixin
from backend.actions.customer_flow.orders import GetCustomerActiveOrderAction
from backend.actions.customer_flow.personalization import GetCustomerBuyAgainAction
from backend.data import CustomerFlowRepository
from helpers.delivery_quotes import quote_vendor_delivery
from products.data.category_repository import CategoryRepository
from products.serializers import CategorySerializer, ProductListSerializer
from vendors.serializers.public import VendorListSerializer
from orders.serializers.coupon_serializers import CouponSerializer


class GetCustomerFlowHomeAction(CustomerLocationMixin):
    repository = CustomerFlowRepository

    def execute(self, request) -> dict:
        address = self.request_address(request)
        serviceability = self.serviceability_payload(request)
        category_ids = CategoryRepository.get_available_customer_category_ids(address=address)
        categories = CategoryRepository.get_customer_visible(category_ids=category_ids)
        stores = self._nearby_stores(request, address)
        store_ids = [store.get('id') for store in stores]
        products = self._products(store_ids=store_ids)
        coupons = self.repository.active_coupons()[:6]
        active_order = GetCustomerActiveOrderAction().execute(request)['active_order']
        category_cards = CategorySerializer(categories[:12], many=True, context={'request': request}).data
        buy_again = GetCustomerBuyAgainAction().execute(request)['results']
        nearby_stores = stores[:12]
        flash_deals = ProductListSerializer(products.filter(compare_price__gt=0)[:12], many=True, context={'request': request}).data
        recommended_products = ProductListSerializer(products[:16], many=True, context={'request': request}).data
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

    def _products(self, store_ids: list[str]):
        products = self.repository.customer_visible_products()
        if store_ids:
            products = products.filter(vendor_id__in=store_ids)
        return products
