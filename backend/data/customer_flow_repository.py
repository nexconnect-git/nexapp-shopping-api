from django.db.models import Q
from django.utils import timezone

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
            .filter(category__is_active=True, category__show_in_customer_ui=True)
            .order_by('-is_featured', '-total_orders', '-average_rating', 'name')
        )

    @staticmethod
    def searchable_products(query='', category_query=None):
        products = ProductRepository.get_all(
            select_related=['vendor', 'category', 'catalog_product'],
            prefetch_related=['images', 'catalog_product__images'],
        ).filter(vendor__status='approved', vendor__is_accepting_orders=True)

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
            .prefetch_related('items')
            .get(pk=order_id, customer=user)
        )

    @staticmethod
    def active_order(user, statuses):
        return (
            Order.objects.filter(customer=user, status__in=statuses)
            .select_related('vendor', 'delivery_address')
            .order_by('-placed_at')
            .first()
        )
