from typing import Dict, Any
from django.db import transaction

from products.models import Product, ProductImage
from vendors.models import Vendor
from .base import BaseAction

class DecreaseStockAction(BaseAction):
    @transaction.atomic
    def execute(self, product_id: str, quantity: int) -> Product:
        product = Product.objects.select_for_update().get(pk=product_id)
        product.stock = max(0, product.stock - quantity)
        product.save(update_fields=["stock"])
        return product


class CreateVendorProductAction(BaseAction):
    def execute(self, vendor_id: str, data: Dict[str, Any]) -> Product:
        vendor = Vendor.objects.get(pk=vendor_id)
        product = Product(vendor=vendor, **data)
        product.save()
        return product


class AddProductImageAction(BaseAction):
    def execute(self, product_id: str, vendor_id: str, image_file, is_primary: bool, is_ai_generated: bool) -> ProductImage:
        product = Product.objects.get(pk=product_id, vendor_id=vendor_id)
        existing_count = product.images.count()

        if existing_count >= 5:
            raise ValueError("Maximum 5 images allowed per product.")

        if is_ai_generated:
            ai_count = product.images.filter(is_ai_generated=True).count()
            if ai_count >= 2:
                raise ValueError("Maximum 2 AI-generated images allowed per product.")

        with transaction.atomic():
            if is_primary:
                product.images.filter(is_primary=True).update(is_primary=False)

            img = ProductImage.objects.create(
                product=product,
                image=image_file,
                is_primary=is_primary or existing_count == 0,
                is_ai_generated=is_ai_generated,
                display_order=existing_count,
            )
        return img


class UpdateStockAction(BaseAction):
    def execute(self, product_id: str, vendor_id: str, stock: int = None, threshold: int = None) -> Product:
        product = Product.objects.get(pk=product_id, vendor_id=vendor_id)
        update_fields = []
        if stock is not None:
            product.stock = stock
            update_fields.append("stock")
        if threshold is not None:
            product.low_stock_threshold = threshold
            update_fields.append("low_stock_threshold")
        if update_fields:
            update_fields.append("updated_at")
            product.save(update_fields=update_fields)
        return product
