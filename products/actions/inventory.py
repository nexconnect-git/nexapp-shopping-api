import logging
from typing import Dict, Any
from django.db import transaction

from products.models import Product, ProductImage
from products.data.product_repository import ProductRepository
from products.data.image_repository import ProductImageRepository
from vendors.models import Vendor
from products.actions.approval import ProductApprovalPolicy
from products.actions.base import BaseAction
from helpers.validators import validate_image_upload
from rest_framework.exceptions import NotFound, ValidationError
from vendors.data.stock_repository import VendorStockRepository

logger = logging.getLogger(__name__)


class DecreaseStockAction(BaseAction):
    @transaction.atomic
    def execute(self, product_id: str, quantity: int) -> Product:
        product = Product.objects.select_for_update().get(pk=product_id)
        prev_stock = product.stock
        product.stock = max(0, product.stock - quantity)
        update_fields = ["stock", "updated_at"]
        if product.stock == 0 and product.status == "active":
            product.status = "sold_out"
            update_fields.append("status")
        product.save(update_fields=update_fields)

        # Notify vendor when stock crosses low_stock_threshold
        threshold = product.low_stock_threshold or 0
        if (
            threshold > 0
            and prev_stock > threshold
            and 0 < product.stock <= threshold
        ):
            try:
                from notifications.models import Notification
                vendor_user = product.vendor.user
                Notification.objects.create(
                    user=vendor_user,
                    title="Low Stock Alert",
                    message=(
                        f"'{product.name}' is running low — only {product.stock} unit(s) remaining "
                        f"(threshold: {threshold})."
                    ),
                    notification_type='system',
                    data={'product_id': str(product.pk), 'stock': product.stock},
                )
            except Exception as exc:
                logger.warning("Could not send low stock notification: %s", exc)

        return product


class CreateVendorProductAction(BaseAction):
    def execute(self, vendor_id: str, data: Dict[str, Any]) -> Product:
        vendor = Vendor.objects.get(pk=vendor_id)
        product = Product(vendor=vendor, **data)
        product.save()
        return product


class ProductImageCommandAction(BaseAction):
    @transaction.atomic
    def execute(self, vendor_id, product_id, command, image_id=None, image_file=None, is_primary=False, inheritance_mode=None):
        product = ProductRepository.locked_by_vendor(vendor_id, product_id)
        if not product:
            raise NotFound('Product not found.')
        if product.approval_status == Product.APPROVAL_STATUS_PENDING:
            raise ValidationError('Images cannot change while the product is awaiting review.')
        if inheritance_mode is not None and inheritance_mode not in {'base_image','vendor_image_only','mixed'}:
            raise ValidationError('Choose a valid image source.')
        repo = ProductImageRepository()
        if command == 'add':
            validate_image_upload(image_file, label='product image')
            count = repo.count(product)
            if count >= 5:
                raise ValidationError('Maximum 5 vendor images allowed per product.')
            if is_primary:
                repo.clear_primary(product)
            image = repo.create(product, image_file, is_primary or count == 0, False, count)
        else:
            image = repo.get_by_id_and_product(image_id, product)
            if not image:
                raise NotFound('Image not found.')
            if command == 'delete':
                primary = image.is_primary
                repo.delete(image)
                if primary:
                    repo.promote_next_to_primary(product)
            elif command == 'primary':
                repo.clear_primary(product)
                repo.make_primary(image)
            else:
                raise ValidationError('Unsupported image action.')
        fields = ['updated_at']
        changes = ['images']
        if inheritance_mode is not None and inheritance_mode != product.inheritance_mode:
            product.inheritance_mode = inheritance_mode
            fields.append('inheritance_mode')
            changes.append('inheritance_mode')
        if product.approval_status in {Product.APPROVAL_STATUS_APPROVED, Product.APPROVAL_STATUS_REJECTED}:
            fields += ProductApprovalPolicy.mark_requires_review(product, changes)
        ProductRepository.save_fields(product, fields)
        return image


class AddProductImageAction(BaseAction):
    def execute(self, product_id, vendor_id, image_file, is_primary=False, is_ai_generated=False, inheritance_mode=None):
        if is_ai_generated:
            raise ValidationError('AI image generation is unavailable.')
        return ProductImageCommandAction().execute(vendor_id, product_id, 'add', image_file=image_file, is_primary=is_primary, inheritance_mode=inheritance_mode)


class UpdateStockAction(BaseAction):
    @transaction.atomic
    def execute(self, product_id: str, vendor_id: str, stock: int = None, threshold: int = None) -> Product:
        for field, value in [('stock', stock), ('low_stock_threshold', threshold)]:
            if value is not None and (type(value) is not int or not 0 <= value <= 2147483647):
                raise ValidationError({field: 'Enter a non-negative whole number.'})
        product = VendorStockRepository().locked(vendor_id, product_id)
        if not product:
            raise NotFound('Product not found.')
        update_fields = []
        if stock is not None:
            product.stock = stock
            update_fields.append("stock")
        if threshold is not None:
            product.low_stock_threshold = threshold
            update_fields.append("low_stock_threshold")
        if update_fields:
            update_fields.append("updated_at")
            VendorStockRepository().save_fields(product, update_fields)
        return product
