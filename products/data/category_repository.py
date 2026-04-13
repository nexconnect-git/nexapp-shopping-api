"""Repository for Category ORM queries."""

from products.models.category import Category


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
