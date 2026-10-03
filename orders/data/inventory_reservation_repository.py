from django.db.models import F
from django.utils import timezone

from orders.models import InventoryReservation
from products.models import Product
from vendors.data.base import BaseRepository
from vendors.models import FulfillmentNodeInventory


class InventoryReservationRepository(BaseRepository):
    def __init__(self):
        super().__init__(InventoryReservation)

    @staticmethod
    def committed_for_release(order):
        # Older orders predate the reservation ledger. Create their ledger once
        # so their first cancellation restores stock and retries remain safe.
        if not InventoryReservation.objects.filter(order=order).exists():
            for item in order.items.select_related('product').all():
                if item.product_id:
                    InventoryReservation.objects.get_or_create(
                        order_item=item,
                        defaults={
                            'order': order, 'product': item.product, 'vendor': order.vendor,
                            'fulfillment_node': order.fulfillment_node, 'quantity': item.quantity,
                            'price_at_reservation': item.product_price,
                            'status': InventoryReservation.STATUS_COMMITTED,
                            'reserved_until': timezone.now(),
                        },
                    )
        return list(InventoryReservation.objects.select_for_update(of=('self',)).select_related(
            'product', 'fulfillment_node',
        ).filter(order=order, status=InventoryReservation.STATUS_COMMITTED))

    @staticmethod
    def restore_product(reservation):
        Product.objects.filter(pk=reservation.product_id).update(stock=F('stock') + reservation.quantity)
        Product.objects.filter(pk=reservation.product_id, status='sold_out').update(status='active')

    @staticmethod
    def restore_node(reservation):
        FulfillmentNodeInventory.objects.filter(
            node_id=reservation.fulfillment_node_id, product_id=reservation.product_id,
        ).update(stock=F('stock') + reservation.quantity, is_available=True)
