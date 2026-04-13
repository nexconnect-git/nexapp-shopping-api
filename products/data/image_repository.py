"""Repository for ProductImage ORM queries."""

from products.models.product import Product
from products.models.product_image import ProductImage


class ProductImageRepository:
    """All ORM access for the ProductImage model lives here."""

    @staticmethod
    def get_by_id(pk) -> ProductImage | None:
        """Fetch a ProductImage by primary key."""
        try:
            return ProductImage.objects.get(pk=pk)
        except ProductImage.DoesNotExist:
            return None

    @staticmethod
    def get_by_id_and_product(pk, product: Product) -> ProductImage | None:
        """Fetch an image belonging to a specific product."""
        try:
            return ProductImage.objects.get(pk=pk, product=product)
        except ProductImage.DoesNotExist:
            return None

    @staticmethod
    def get_all(product: Product):
        """Return all images for the given product."""
        return product.images.all()

    @staticmethod
    def count(product: Product) -> int:
        """Return the total number of images for the given product."""
        return product.images.count()

    @staticmethod
    def count_ai(product: Product) -> int:
        """Return the number of AI-generated images for the given product."""
        return product.images.filter(is_ai_generated=True).count()

    @staticmethod
    def clear_primary(product: Product) -> None:
        """Clear the is_primary flag on all images for the given product."""
        product.images.filter(is_primary=True).update(is_primary=False)

    @staticmethod
    def create(product: Product, image_file, is_primary: bool,
               is_ai_generated: bool, display_order: int) -> ProductImage:
        """Create and persist a new ProductImage.

        Args:
            product: Owning product.
            image_file: The image file to store.
            is_primary: Whether this is the primary image.
            is_ai_generated: Whether the image was AI-generated.
            display_order: Sort order within the product's image set.

        Returns:
            The newly created ProductImage.
        """
        return ProductImage.objects.create(
            product=product,
            image=image_file,
            is_primary=is_primary,
            is_ai_generated=is_ai_generated,
            display_order=display_order,
        )

    @staticmethod
    def promote_next_to_primary(product: Product) -> None:
        """Set the first remaining image as primary.

        Args:
            product: The product whose images need a new primary.
        """
        first = product.images.first()
        if first:
            first.is_primary = True
            first.save(update_fields=["is_primary"])

    @staticmethod
    def delete(instance: ProductImage) -> None:
        """Delete the image file and the database record."""
        instance.image.delete(save=False)
        instance.delete()
