from decimal import Decimal, InvalidOperation

from django.db.models import F, Q
from django.utils import timezone

from orders.data import CustomerRecommendationRepository
from orders.models import Coupon, Order, OrderItem
from products.data.product_repository import ProductRepository
from vendors.models import Vendor


class CustomerFlowRepository:
    """Reusable query layer for customer app composition actions."""

    @staticmethod
    def open_approved_stores():
        return Vendor.objects.filter(
            status='approved',
            is_open=True,
            is_accepting_orders=True,
        )

    @staticmethod
    def customer_visible_products():
        return (
            ProductRepository.get_all(
                select_related=['vendor', 'category', 'catalog_product'],
                prefetch_related=['images', 'catalog_product__images'],
            )
            .filter(
                vendor__status='approved',
                vendor__is_open=True,
                vendor__is_accepting_orders=True,
                category__is_active=True,
                category__show_in_customer_ui=True,
            )
            .order_by('-is_featured', '-total_orders', '-average_rating', 'name')
        )

    @staticmethod
    def searchable_products(query='', category_query=None):
        products = ProductRepository.get_all(
            select_related=['vendor', 'category', 'catalog_product'],
            prefetch_related=['images', 'catalog_product__images'],
        ).filter(
            vendor__status='approved',
            vendor__is_open=True,
            vendor__is_accepting_orders=True,
        )

        if query:
            products = products.filter(
                Q(name__icontains=query)
                | Q(search_keywords__icontains=query)
                | Q(description__icontains=query)
                | Q(brand__icontains=query)
                | Q(category__name__icontains=query)
            )
        if category_query is not None:
            products = products.filter(category_query)

        return products.order_by('-is_featured', '-total_orders', '-average_rating', 'price')

    @staticmethod
    def filtered_search_products(products, params):
        if str(params.get('in_stock', '')).lower() in ('true', '1', 'yes'):
            products = products.filter(stock__gt=0)
        if str(params.get('instant_only', '')).lower() in ('true', '1', 'yes'):
            products = products.filter(is_instant_delivery=True)
        if str(params.get('offers', '')).lower() in ('true', '1', 'yes'):
            products = products.filter(compare_price__gt=0)
        discount = params.get('min_discount')
        if discount:
            try:
                percentage = Decimal(discount)
                if not percentage.is_finite() or not 0 <= percentage <= 100:
                    return products.none()
                products = products.filter(compare_price__gt=0, price__lte=F('compare_price') * (1 - percentage / 100))
            except (InvalidOperation, TypeError, ValueError):
                return products.none()
        for field, key in [('price__gte', 'min_price'), ('price__lte', 'max_price'), ('average_rating__gte', 'rating')]:
            if params.get(key):
                products = products.filter(**{field: params[key]})
        ordering = {
            'price_low_high': ('price', 'name', 'id'),
            'price_high_low': ('-price', 'name', 'id'),
            'rating': ('-average_rating', '-total_orders', 'id'),
            'offers': ('-compare_price', 'price', 'id'),
        }.get(params.get('sort'), ('-total_orders', 'name', 'id'))
        return products.order_by(*ordering)

    @staticmethod
    def products_for_vendors(products, vendor_ids):
        return products.filter(vendor_id__in=vendor_ids) if vendor_ids else products.none()

    @staticmethod
    def searchable_stores(query='', category_query=None):
        stores = CustomerFlowRepository.open_approved_stores()
        if query:
            stores = stores.filter(
                Q(store_name__icontains=query)
                | Q(description__icontains=query)
                | Q(products__name__icontains=query)
                | Q(products__search_keywords__icontains=query)
            )
        if category_query is not None:
            stores = stores.filter(category_query)
        return stores.distinct()

    @staticmethod
    def active_coupons(subtotal=None):
        now = timezone.now()
        coupons = Coupon.objects.filter(is_active=True, valid_from__lte=now).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gte=now)
        )
        if subtotal is not None:
            coupons = coupons.filter(min_order_amount__lte=subtotal)
        return coupons.order_by('display_order', '-created_at')

    @staticmethod
    def ordered_product_ids(user):
        return (
            OrderItem.objects.filter(order__customer=user, product__isnull=False)
            .order_by('-order__placed_at')
            .values_list('product_id', flat=True)
            .distinct()[:16]
        )

    @staticmethod
    def order_confirmation_order(user, order_id):
        return (
            Order.objects.select_related('vendor', 'delivery_address')
            .prefetch_related('items__product__images', 'items__product__catalog_product__images')
            .filter(pk=order_id, customer=user)
            .first()
        )

    @staticmethod
    def order_confirmation_items(order):
        return list(order.items.all())

    @staticmethod
    def active_order(user, statuses):
        return (
            Order.objects.filter(customer=user, status__in=statuses)
            .select_related('vendor', 'delivery_address')
            .order_by('-placed_at')
            .first()
        )

    @staticmethod
    def recommendation_snapshot(user):
        return CustomerRecommendationRepository.get_for_user(user)
