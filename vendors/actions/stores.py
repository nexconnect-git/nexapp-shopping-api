from django.db import transaction

from vendors.actions.base import BaseAction
from vendors.data.stock_repository import VendorStockRepository

class SetStoreStatusAction(BaseAction):
    def execute(self, vendor, is_open: bool, closing_time: str = None):
        if is_open:
            if not closing_time:
                raise ValueError("closing_time is required when opening the store.")
            vendor.is_open = True
            vendor.closing_time = closing_time
            vendor.save(update_fields=["is_open", "closing_time", "updated_at"])
        else:
            vendor.is_open = False
            vendor.save(update_fields=["is_open", "updated_at"])
        return vendor


class BulkUpdateStockAction(BaseAction):
    @transaction.atomic
    def execute(self, vendor, updates: list):
        if not isinstance(updates, list) or len(updates) > 500:
            raise ValueError('Use a list of at most 500 stock updates.')
        
        updated = []
        errors = []
        repository = VendorStockRepository()
        seen = set()
        for index, entry in enumerate(updates):
            product_id = entry.get('id') if isinstance(entry, dict) else None
            stock = entry.get('stock') if isinstance(entry, dict) else None
            error = None
            current_stock = None
            if type(stock) is not int or stock < 0 or stock > 2147483647:
                error = 'Stock must be a non-negative integer.'
            elif str(product_id) in seen:
                error = 'Product appears more than once in this request.'
            else:
                product = repository.locked(vendor, product_id)
                if product is None:
                    error = 'Product not found in your store.'
                elif 'expected_stock' in entry and (type(entry['expected_stock']) is not int or entry['expected_stock'] != product.stock):
                    error = f'Stock changed elsewhere to {product.stock}. Review the current quantity before retrying.'
                    current_stock = product.stock
                else:
                    repository.save_stock(product, stock)
                    updated.append(str(product.pk))
                    seen.add(str(product.pk))
            if error:
                errors.append({'id': str(product_id) if product_id else None, 'index': index, 'field': 'stock', 'message': error, **({'current_stock': current_stock} if current_stock is not None else {})})

        return updated, errors
