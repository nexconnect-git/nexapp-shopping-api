from django.core.exceptions import ValidationError
from django.db.models import F

from products.models import Product
from vendors.data.base import BaseRepository


class VendorStockRepository(BaseRepository):
    def __init__(self):
        super().__init__(Product)

    def locked(self, vendor, product_id):
        try:
            return self.model.objects.select_for_update().filter(pk=product_id, vendor=vendor).first()
        except (ValidationError, ValueError, TypeError):
            return None

    def save_stock(self, product, stock):
        product.stock = stock
        product.save(update_fields=['stock', 'updated_at'])
        return product

    def save_fields(self, product, fields):
        product.save(update_fields=fields)
        return product

    def low_stock(self, vendor):
        return self.filter(vendor=vendor, low_stock_threshold__gt=0, stock__lte=F('low_stock_threshold'))
