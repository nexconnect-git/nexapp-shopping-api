"""Repository for ProductReview ORM queries."""

from products.models.product_review import ProductReview


class ProductReviewRepository:
    """All ORM access for the ProductReview model lives here."""

    @staticmethod
    def get_by_id(pk) -> ProductReview | None:
        """Fetch a ProductReview by primary key."""
        try:
            return ProductReview.objects.get(pk=pk)
        except ProductReview.DoesNotExist:
            return None

    @staticmethod
    def get_all():
        """Return all product reviews."""
        return ProductReview.objects.all()

    @staticmethod
    def filter(product_id=None):
        """Return reviews optionally scoped to a product.

        Args:
            product_id: UUID of the product to scope reviews to.

        Returns:
            Filtered queryset.
        """
        qs = ProductReview.objects.all()
        if product_id:
            qs = qs.filter(product_id=product_id)
        return qs

    @staticmethod
    def create(product, customer, **kwargs) -> ProductReview:
        """Create and persist a new ProductReview."""
        return ProductReview.objects.create(
            product=product, customer=customer, **kwargs
        )

    @staticmethod
    def update(instance: ProductReview, **kwargs) -> ProductReview:
        """Apply field updates to ``instance`` and save."""
        for field, value in kwargs.items():
            setattr(instance, field, value)
        instance.save()
        return instance

    @staticmethod
    def delete(instance: ProductReview) -> None:
        """Delete ``instance`` from the database."""
        instance.delete()
