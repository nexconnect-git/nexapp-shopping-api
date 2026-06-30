"""Repository for Category ORM queries."""

from django.db import models

from helpers.delivery_quotes import quote_vendor_delivery
from products.models.category import Category
from products.models.product import Product
from products.data.product_repository import ProductRepository
from vendors.models import Vendor


class CategoryRepository:
    """All ORM access for the Category model lives here."""

    @staticmethod
    def get_by_id(pk) -> Category | None:
        """Fetch a Category by primary key, returning None on miss."""
        try:
            return Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return None

    @staticmethod
    def get_all():
        """Return all categories ordered by display_order, name."""
        return Category.objects.all().order_by("display_order", "name")

    @staticmethod
    def get_active_root():
        """Return active root (no parent) categories."""
        return Category.objects.filter(is_active=True, parent__isnull=True)

    @staticmethod
    def get_available_customer_category_ids(vendor_id=None, address=None, fulfillment_node=None) -> set:
        """Return category ids that have orderable customer products for the optional store/location."""
        products = Product.objects.filter(
            vendor__status="approved",
            category__isnull=False,
            category__is_active=True,
            category__show_in_customer_ui=True,
            **ProductRepository.customer_visible_filter(),
        ).select_related("category", "category__parent", "vendor")

        if vendor_id:
            products = products.filter(vendor_id=vendor_id)

        if fulfillment_node:
            products = products.filter(
                fulfillment_inventory__node=fulfillment_node,
                fulfillment_inventory__is_available=True,
                fulfillment_inventory__stock__gt=0,
                fulfillment_inventory__reserved_stock__lt=models.F("fulfillment_inventory__stock"),
            )

        if address:
            vendor_ids = products.values_list("vendor_id", flat=True).distinct()
            serviceable_vendor_ids = []
            for vendor in Vendor.objects.filter(id__in=vendor_ids, status="approved"):
                try:
                    quote = quote_vendor_delivery(vendor, address)
                except Exception:
                    continue
                if quote.is_serviceable:
                    serviceable_vendor_ids.append(vendor.id)
            products = products.filter(vendor_id__in=serviceable_vendor_ids)

        category_ids = set()
        for category_id, parent_id in products.values_list("category_id", "category__parent_id").distinct():
            if category_id:
                category_ids.add(category_id)
            if parent_id:
                category_ids.add(parent_id)
        return category_ids

    @staticmethod
    def get_customer_visible(category_ids=None):
        """Return active root categories visible to customers and backed by available products."""
        if category_ids is None:
            category_ids = CategoryRepository.get_available_customer_category_ids()
        if not category_ids:
            return Category.objects.none()
        return (
            Category.objects.filter(
                is_active=True,
                show_in_customer_ui=True,
                parent__isnull=True,
            )
            .filter(models.Q(id__in=category_ids) | models.Q(children__id__in=category_ids))
            .distinct()
            .order_by("display_order", "name")
        )

    @staticmethod
    def filter(parent_id=None, is_root: bool = False):
        """Filter categories by optional constraints.

        Args:
            parent_id: UUID of parent to filter children by.
            is_root: When True, return only categories with no parent.

        Returns:
            A filtered queryset.
        """
        qs = Category.objects.all().order_by("display_order", "name")
        if is_root:
            return qs.filter(parent__isnull=True)
        if parent_id:
            return qs.filter(parent_id=parent_id)
        return qs

    @staticmethod
    def create(**kwargs) -> Category:
        """Create and return a new Category."""
        return Category.objects.create(**kwargs)

    @staticmethod
    def update(instance: Category, **kwargs) -> Category:
        """Apply field updates to ``instance`` and save."""
        for field, value in kwargs.items():
            setattr(instance, field, value)
        instance.save()
        return instance

    @staticmethod
    def delete(instance: Category) -> None:
        """Delete ``instance`` from the database."""
        instance.delete()
