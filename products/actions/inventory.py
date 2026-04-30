import logging
from typing import Dict, Any
from django.db import transaction

from products.models import Product, ProductImage
from vendors.models import Vendor
from products.actions.approval import ProductApprovalPolicy
from .base import BaseAction

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
            if product.approval_status in {
                Product.APPROVAL_STATUS_APPROVED,
                Product.APPROVAL_STATUS_REJECTED,
                Product.APPROVAL_STATUS_PENDING,
            }:
                update_fields = ProductApprovalPolicy.mark_requires_review(product, ["images"])
                update_fields.append("updated_at")
                product.save(update_fields=sorted(set(update_fields)))
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
