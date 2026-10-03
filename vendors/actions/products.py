"""Owner-scoped product removal with preserved inventory/order history."""
from django.db import transaction
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import NotFound, ValidationError

from products.data.product_repository import ProductRepository


class DeleteVendorProductAction:
    def execute(self, vendor, product_id):
        with transaction.atomic():
            product = ProductRepository.locked_by_vendor(vendor.pk, product_id)
            if product is None:
                raise NotFound('Product not found.')
            try:
                ProductRepository.delete(product)
            except ProtectedError:
                raise ValidationError({
                    'detail': 'This product has protected order or inventory history and cannot be removed. Make it unavailable in the editor to stop selling it.'
                })
