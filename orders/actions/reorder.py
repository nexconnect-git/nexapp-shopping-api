from django.db import transaction

from orders.actions.base import BaseAction
from orders.data.cart_repo import CartRepository
from orders.data.order_repo import OrderRepository
from orders.models import Order


class ReorderAction(BaseAction):
    @transaction.atomic
    def execute(self, user, order_id, preview=False):
        try:
            order = OrderRepository.get_reorder_snapshot(user, order_id)
        except Order.DoesNotExist:
            raise ValueError('Order not found.')
        available, changes, skipped = [], [], []
        for item in OrderRepository.reorder_items(order):
            product = item.product
            if (not product or not product.catalog_product_id or not product.is_available or product.stock < product.min_order_quantity
                    or product.status != 'active' or product.approval_status != 'approved'
                    or product.vendor.status != 'approved'):
                skipped.append(item.product_name)
                continue
            quantity = min(max(item.quantity, product.min_order_quantity), product.stock)
            available.append((product, quantity))
            changes.append({
                'product_id': str(product.pk), 'name': product.name, 'previous_price': str(item.product_price),
                'price': str(product.price), 'previous_quantity': item.quantity,
                'quantity': quantity,
            })
        summary = {'items': changes, 'skipped': skipped}
        if preview:
            return summary
        if not available:
            raise ValueError('No items from this order are currently available. Your basket is unchanged.')
        CartRepository.clear_cart(user)
        cart, _ = CartRepository.get_or_create_cart(user)
        for product, quantity in available:
            CartRepository.add_item(cart, product, quantity)
        return {'cart': cart, **summary}
