from django.db.models import F
from django.utils import timezone

from accounts.models import Address, User
from backend.services import RecommendationServiceClient
from orders.actions.base import BaseAction
from orders.data import CustomerRecommendationRepository
from orders.models import OrderItem
from products.data.product_repository import ProductRepository
from vendors.models import Vendor


class RefreshCustomerRecommendationsAction(BaseAction):
    """Precompute customer recommendations so UI requests stay cheap."""

    repository = CustomerRecommendationRepository

    def execute(self, user_id=None, limit=24):
        users = User.objects.filter(role='customer', is_active=True)
        if user_id:
            users = users.filter(id=user_id)

        client = RecommendationServiceClient()
        refreshed = 0
        for user in users.iterator():
            address = self._default_address(user)
            location = self._location_payload(address)
            recommended_product_ids = self._ranked_product_ids(
                client=client,
                user=user,
                recommendation_type='recommended',
                fallback_ids=self._fallback_product_ids(user, limit),
                limit=limit,
                location=location,
            )
            flash_deal_product_ids = self._ranked_product_ids(
                client=client,
                user=user,
                recommendation_type='flash_deals',
                fallback_ids=self._fallback_flash_deal_ids(limit),
                limit=limit,
                location=location,
            )
            recommended_store_ids = self._ranked_store_ids(
                client=client,
                user=user,
                fallback_ids=self._fallback_store_ids(address, limit),
                limit=limit,
                location=location,
            )
            store_product_ids = self._store_product_recommendations(
                user=user,
                address=address,
                recommended_product_ids=recommended_product_ids,
                flash_deal_product_ids=flash_deal_product_ids,
                recommended_store_ids=recommended_store_ids,
                limit=min(limit, 16),
            )
            self.repository.upsert_for_user(
                user,
                recommended_product_ids=recommended_product_ids,
                flash_deal_product_ids=flash_deal_product_ids,
                recommended_store_ids=recommended_store_ids,
                metadata={
                    'source': 'scheduled',
                    'service_enabled': client.enabled,
                    'limit': limit,
                    'store_product_ids': store_product_ids,
                    'generated_at': timezone.now().isoformat(),
                },
            )
            refreshed += 1

        return {'refreshed': refreshed, 'limit': limit}

    def _ranked_product_ids(self, *, client, user, recommendation_type, fallback_ids, limit, location):
        ranked_items = client.user_recommendations(
            user_id=str(user.id),
            limit=max(limit * 3, limit),
            recommendation_type=recommendation_type,
            location=location,
        )
        ranked_ids = [item['product_id'] for item in ranked_items if item.get('product_id')]
        return self._merge_unique_ids(ranked_ids, fallback_ids, limit)

    def _ranked_store_ids(self, *, client, user, fallback_ids, limit, location):
        ranked_items = client.store_recommendations(
            user_id=str(user.id),
            limit=max(limit * 2, limit),
            location=location,
        )
        ranked_ids = [item['store_id'] for item in ranked_items if item.get('store_id')]
        return self._merge_unique_ids(ranked_ids, fallback_ids, limit)

    def _fallback_product_ids(self, user, limit):
        ordered_ids = list(
            OrderItem.objects.filter(order__customer=user, product__isnull=False)
            .order_by('-order__placed_at')
            .values_list('product_id', flat=True)
            .distinct()[:limit]
        )
        popular_ids = list(
            ProductRepository.get_all()
            .order_by('-is_featured', '-total_orders', '-average_rating', 'name')
            .values_list('id', flat=True)[:limit]
        )
        return self._merge_unique_ids(ordered_ids, popular_ids, limit)

    def _fallback_flash_deal_ids(self, limit):
        return [
            str(product_id)
            for product_id in ProductRepository.get_all()
            .filter(compare_price__gt=F('price'))
            .order_by('-total_orders', '-average_rating', 'price')
            .values_list('id', flat=True)[:limit]
        ]

    def _fallback_store_ids(self, address, limit):
        stores = Vendor.objects.filter(
            status='approved',
            is_open=True,
            is_accepting_orders=True,
        )
        if address:
            same_area = stores.filter(city__iexact=address.city, state__iexact=address.state)
            if same_area.exists():
                stores = same_area
        return [
            str(store_id)
            for store_id in stores.order_by('-is_featured', '-average_rating', 'store_name')
            .values_list('id', flat=True)[:limit]
        ]

    def _store_product_recommendations(
        self,
        *,
        user,
        address,
        recommended_product_ids,
        flash_deal_product_ids,
        recommended_store_ids,
        limit,
    ):
        profile = self._taste_profile(user)
        stores = Vendor.objects.filter(
            status='approved',
            is_open=True,
            is_accepting_orders=True,
        )
        if address:
            same_area = stores.filter(city__iexact=address.city, state__iexact=address.state)
            if same_area.exists():
                stores = same_area
        fallback_store_ids = list(stores.values_list('id', flat=True))
        store_ids = self._merge_unique_ids(
            recommended_store_ids,
            fallback_store_ids,
            max(len(fallback_store_ids), len(recommended_store_ids), 1),
        )
        ranked_by_store = {}
        for store_id in store_ids:
            products = list(
                ProductRepository.get_all(select_related=['category'])
                .filter(
                    vendor_id=store_id,
                    category__is_active=True,
                    category__show_in_customer_ui=True,
                )
                .order_by('-is_featured', '-total_orders', '-average_rating', 'name')[:120]
            )
            ranked_ids = self._rank_store_products(
                products=products,
                profile=profile,
                recommended_product_ids=recommended_product_ids,
                flash_deal_product_ids=flash_deal_product_ids,
                limit=limit,
            )
            if ranked_ids:
                ranked_by_store[str(store_id)] = ranked_ids
        return ranked_by_store

    def _taste_profile(self, user):
        profile = {
            'product_ids': set(),
            'category_weights': {},
            'brand_weights': {},
        }
        items = (
            OrderItem.objects.filter(order__customer=user, product__isnull=False)
            .select_related('product', 'product__category')
            .order_by('-order__placed_at')[:120]
        )
        weight = 120
        for item in items:
            product = item.product
            profile['product_ids'].add(str(product.id))
            if product.category_id:
                category_id = str(product.category_id)
                profile['category_weights'][category_id] = (
                    profile['category_weights'].get(category_id, 0) + weight
                )
            brand = (product.brand or item.product_brand or '').strip().lower()
            if brand:
                profile['brand_weights'][brand] = profile['brand_weights'].get(brand, 0) + weight
            weight = max(weight - 1, 1)
        return profile

    def _rank_store_products(self, *, products, profile, recommended_product_ids, flash_deal_product_ids, limit):
        recommended_rank = {
            str(product_id): index
            for index, product_id in enumerate(recommended_product_ids or [])
        }
        flash_rank = {
            str(product_id): index
            for index, product_id in enumerate(flash_deal_product_ids or [])
        }

        def score(product):
            product_id = str(product.id)
            value = 0
            if product_id in recommended_rank:
                value += 2000 - recommended_rank[product_id]
            if product_id in flash_rank:
                value += 600 - flash_rank[product_id]
            if product_id in profile['product_ids']:
                value += 1200
            if product.category_id:
                value += profile['category_weights'].get(str(product.category_id), 0)
            brand = (product.brand or '').strip().lower()
            if brand:
                value += profile['brand_weights'].get(brand, 0)
            if product.is_featured:
                value += 80
            if product.compare_price and product.compare_price > product.price:
                value += 50
            value += min(int(product.total_orders or 0), 100)
            value += int(float(product.average_rating or 0) * 10)
            return value

        ranked = sorted(products, key=lambda product: (-score(product), product.name.lower()))
        return [str(product.id) for product in ranked[:limit]]

    def _default_address(self, user):
        return (
            Address.objects.filter(user=user, is_default=True).first()
            or Address.objects.filter(user=user).order_by('-created_at').first()
        )

    def _location_payload(self, address):
        if not address:
            return {}
        return {
            'lat': str(address.latitude) if address.latitude is not None else None,
            'lng': str(address.longitude) if address.longitude is not None else None,
            'city': address.city or '',
            'state': address.state or '',
            'postal_code': address.postal_code or '',
        }

    def _merge_unique_ids(self, primary_ids, fallback_ids, limit):
        seen = set()
        merged = []
        for raw_id in [*primary_ids, *fallback_ids]:
            value = str(raw_id)
            if not value or value in seen:
                continue
            seen.add(value)
            merged.append(value)
            if len(merged) >= limit:
                break
        return merged
