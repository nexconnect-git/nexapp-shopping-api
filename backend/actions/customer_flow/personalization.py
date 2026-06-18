from orders.data.cart_repo import CartRepository
from products.data.product_repository import ProductRepository
from products.serializers import ProductListSerializer

from backend.data import CustomerFlowRepository


class GetCustomerBuyAgainAction:
    repository = CustomerFlowRepository

    def execute(self, request) -> dict:
        if not getattr(request.user, 'is_authenticated', False):
            return {'results': []}
        product_ids = self.repository.ordered_product_ids(request.user)
        products = ProductRepository.get_all(
            select_related=['vendor', 'category', 'catalog_product'],
            prefetch_related=['images', 'catalog_product__images'],
        ).filter(id__in=product_ids, vendor__status='approved', vendor__is_accepting_orders=True)
        return {'results': ProductListSerializer(products, many=True, context={'request': request}).data}


class GetCustomerCartSuggestionsAction:
    def execute(self, request) -> dict:
        cart, _ = CartRepository.get_or_create_cart(request.user)
        items = list(cart.items.select_related('product__vendor', 'product__category').all())
        if not items:
            return {'same_store_add_ons': [], 'frequently_bought_together': [], 'buy_again': [], 'replacements': []}
        store = items[0].product.vendor
        cart_product_ids = [item.product_id for item in items]
        categories = [item.product.category_id for item in items if item.product.category_id]
        suggestions = ProductRepository.get_all(
            select_related=['vendor', 'category', 'catalog_product'],
            prefetch_related=['images', 'catalog_product__images'],
        ).filter(vendor=store).exclude(id__in=cart_product_ids)
        add_ons = suggestions.order_by('-total_orders', '-average_rating')[:12]
        replacements = suggestions.filter(category_id__in=categories).order_by('-average_rating')[:8]
        return {
            'same_store_add_ons': ProductListSerializer(add_ons, many=True, context={'request': request}).data,
            'frequently_bought_together': ProductListSerializer(replacements, many=True, context={'request': request}).data,
            'buy_again': GetCustomerBuyAgainAction().execute(request)['results'],
            'replacements': ProductListSerializer(replacements, many=True, context={'request': request}).data,
        }
