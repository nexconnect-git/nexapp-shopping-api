"""Repository for Product ORM queries."""

from django.db import transaction
from django.db.models import F

from products.models.product import Product


class ProductRepository:
    """All ORM access for the Product model lives here."""
    CUSTOMER_VISIBLE_APPROVAL_STATUS = Product.APPROVAL_STATUS_APPROVED

    @staticmethod
    def get_by_id(pk, select_related=None) -> Product | None:
        """Fetch a Product by primary key.

        Args:
            pk: UUID primary key.
            select_related: Optional list of related fields to select.

        Returns:
            Product instance or None.
        """
        try:
            qs = Product.objects
            if select_related:
                qs = qs.select_related(*select_related)
            return qs.get(pk=pk)
        except Product.DoesNotExist:
            return None

    @staticmethod
    def get_by_id_and_vendor(pk, vendor) -> Product | None:
        """Fetch a product belonging to a specific vendor."""
        try:
            return Product.objects.get(pk=pk, vendor=vendor)
        except Product.DoesNotExist:
            return None

    @staticmethod
    def get_all(select_related=None, prefetch_related=None):
        """Return all products with optional related data fetching."""
        qs = Product.objects.filter(
            approval_status=ProductRepository.CUSTOMER_VISIBLE_APPROVAL_STATUS,
            status="active",
            is_available=True,
            stock__gt=0,
        )
        if select_related:
            qs = qs.select_related(*select_related)
        if prefetch_related:
            qs = qs.prefetch_related(*prefetch_related)
        return qs

    @staticmethod
    def get_featured():
        """Return featured, available products."""
        return Product.objects.filter(
            is_featured=True,
            is_available=True,
            status="active",
            stock__gt=0,
            approval_status=ProductRepository.CUSTOMER_VISIBLE_APPROVAL_STATUS,
        )

    @staticmethod
    def get_low_stock(vendor):
        """Return products for a vendor whose stock is at or below threshold."""
        return Product.objects.filter(
            vendor=vendor,
            stock__lte=F("low_stock_threshold"),
        ).order_by("stock")

    @staticmethod
    def filter(category=None, vendor=None, search=None, min_price=None,
               max_price=None, is_available=None):
        """Filter products by optional criteria.

        Args:
            category: Category slug string.
            vendor: Vendor UUID string.
            search: Name substring search.
            min_price: Minimum price filter.
            max_price: Maximum price filter.
            is_available: Boolean availability filter.

        Returns:
            Filtered queryset with vendor, category, and images pre-fetched.
        """
        qs = Product.objects.select_related("vendor", "category").prefetch_related("images")
        qs = qs.filter(approval_status=ProductRepository.CUSTOMER_VISIBLE_APPROVAL_STATUS)
        qs = qs.filter(status="active", stock__gt=0)
        if category:
            qs = qs.filter(category__slug=category)
        if vendor:
            qs = qs.filter(vendor_id=vendor)
        if search:
            qs = qs.filter(name__icontains=search)
        if min_price:
            qs = qs.filter(price__gte=min_price)
        if max_price:
            qs = qs.filter(price__lte=max_price)
        if is_available is not None:
            qs = qs.filter(is_available=is_available)
        return qs

    @staticmethod
    def create(vendor, **kwargs) -> Product:
        """Create and persist a new product for the given vendor."""
        return Product.objects.create(vendor=vendor, **kwargs)

    @staticmethod
    def update(instance: Product, update_fields=None, **kwargs) -> Product:
        """Apply field updates to ``instance`` and save.

        Args:
            instance: The Product to update.
            update_fields: Optional list of field names for partial save.
            **kwargs: Field values to set.

        Returns:
            Updated Product instance.
        """
        for field, value in kwargs.items():
            setattr(instance, field, value)
        if update_fields:
            instance.save(update_fields=update_fields)
        else:
            instance.save()
        return instance

    @staticmethod
    def delete(instance: Product) -> None:
        """Delete ``instance`` from the database."""
        instance.delete()

    @staticmethod
    def decrease_stock(product_id: str, quantity: int) -> Product:
        """Decrease stock atomically, flooring at zero.

        Args:
            product_id: UUID primary key of the product.
            quantity: Units to subtract.

        Returns:
            Updated Product instance.
        """
        with transaction.atomic():
            product = Product.objects.select_for_update().get(pk=product_id)
            product.stock = max(0, product.stock - quantity)
            product.save(update_fields=["stock"])
            return product
