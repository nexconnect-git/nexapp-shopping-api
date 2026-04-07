"""Service layer for the products app.

Encapsulates stock management, product creation, and image upload logic,
keeping those operations reusable and independently testable.
"""

import logging
from typing import Dict, Any, List

from django.db import transaction
from django.core.files.base import ContentFile

from products.models import Product, Category, ProductImage
from vendors.models import Vendor

logger = logging.getLogger(__name__)


class ProductService:
    """Stateless service class for product-related business operations."""

    @staticmethod
    def decrease_stock(product_id: str, quantity: int) -> Product:
        """Decrease a product's stock level by the given quantity (thread-safe).

        Uses ``select_for_update`` inside an atomic transaction to prevent
        race conditions when multiple orders are placed concurrently.

        Args:
            product_id: UUID primary key of the product.
            quantity: Number of units to remove from stock.

        Returns:
            The updated ``Product`` instance (stock floored at 0).
        """
        with transaction.atomic():
            product = Product.objects.select_for_update().get(pk=product_id)
            product.stock = max(0, product.stock - quantity)
            product.save(update_fields=["stock"])
            return product

    @staticmethod
    def get_active_categories() -> List[Category]:
        """Return all active root categories (no parent).

        Returns:
            A list of active top-level ``Category`` instances.
        """
        return list(Category.objects.filter(is_active=True, parent__isnull=True))

    @staticmethod
    def create_product_for_vendor(vendor_id: str, data: Dict[str, Any]) -> Product:
        """Create and persist a new product belonging to the specified vendor.

        Args:
            vendor_id: UUID primary key of the owning vendor.
            data: Dictionary of product field values (excluding ``vendor``).

        Returns:
            The newly created ``Product`` instance.
        """
        vendor = Vendor.objects.get(pk=vendor_id)
        product = Product(vendor=vendor, **data)
        product.save()
        return product

    @staticmethod
    def add_image_to_product(
        product_id: str,
        vendor_id: str,
        image_file,
        is_primary: bool,
        is_ai_generated: bool,
    ) -> ProductImage:
        """Attach an image to a product, enforcing per-product image limits.

        Rules enforced:
        - Maximum 5 images per product.
        - Maximum 2 AI-generated images per product.
        - If ``is_primary`` is ``True``, all existing primary flags are cleared.

        Args:
            product_id: UUID primary key of the target product.
            vendor_id: UUID primary key of the vendor (ownership check).
            image_file: The uploaded file object.
            is_primary: Whether this image should become the primary image.
            is_ai_generated: Whether the image was AI-generated.

        Returns:
            The newly created ``ProductImage`` instance.

        Raises:
            ValueError: If the image limit or AI-image limit would be exceeded.
        """
        product = Product.objects.get(pk=product_id, vendor_id=vendor_id)
        existing_count = product.images.count()

        if existing_count >= 5:
            raise ValueError("Maximum 5 images allowed per product.")

        if is_ai_generated:
            ai_count = product.images.filter(is_ai_generated=True).count()
            if ai_count >= 2:
                raise ValueError(
                    "Maximum 2 AI-generated images allowed per product."
                )

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

    @staticmethod
    def update_stock(
        product_id: str,
        vendor_id: str,
        stock: int = None,
        threshold: int = None,
    ) -> Product:
        """Update stock level and/or low-stock threshold for a product.

        Only the fields explicitly provided (not ``None``) are written.

        Args:
            product_id: UUID primary key of the product.
            vendor_id: UUID primary key of the owning vendor (ownership check).
            stock: New absolute stock count, or ``None`` to leave unchanged.
            threshold: New low-stock alert threshold, or ``None`` to leave unchanged.

        Returns:
            The updated ``Product`` instance.
        """
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
