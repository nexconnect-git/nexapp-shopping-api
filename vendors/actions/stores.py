from vendors.actions.base import BaseAction
from products.models import Product

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
    def execute(self, vendor, updates: list):
        if not isinstance(updates, list):
            raise ValueError("updates must be a list.")
        
        updated = []
        errors = []
        for entry in updates:
            product_id = entry.get("id")
            new_stock = entry.get("stock")
            if product_id is None or new_stock is None:
                continue
            try:
                product = Product.objects.get(pk=product_id, vendor=vendor)
                product.stock = max(0, int(new_stock))
                product.save(update_fields=["stock"])
                updated.append(str(product.id))
            except (Product.DoesNotExist, ValueError):
                errors.append(str(product_id))

        return updated, errors
