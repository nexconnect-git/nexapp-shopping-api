"""Utility helpers for the products app."""

from django.utils.text import slugify

from products.models.product import Product


def generate_unique_slug(base: str, instance=None) -> str:
    """Generate a unique slug for a Product derived from ``base``.

    Appends an incrementing suffix (``-1``, ``-2``, …) until the slug
    is unique in the ``Product`` table, excluding ``instance`` if given.

    Args:
        base: The base string to slugify.
        instance: Existing ``Product`` to exclude from the uniqueness check.

    Returns:
        A unique slug string.
    """
    slug = slugify(base)
    queryset = Product.objects.all()
    if instance:
        queryset = queryset.exclude(pk=instance.pk)
    candidate, n = slug, 1
    while queryset.filter(slug=candidate).exists():
        candidate = f"{slug}-{n}"
        n += 1
    return candidate


def is_low_stock(product) -> bool:
    """Return True if a product's stock is at or below its low-stock threshold.

    Args:
        product: A ``Product`` instance.

    Returns:
        True when ``stock <= low_stock_threshold``, False otherwise.
    """
    return product.stock <= product.low_stock_threshold
