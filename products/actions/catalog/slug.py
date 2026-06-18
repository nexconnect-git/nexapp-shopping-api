from django.utils.text import slugify

from products.models import CatalogProduct


class CatalogSlugMixin:
    def unique_catalog_slug(self, name, instance=None):
        base = slugify(name) or 'catalog-product'
        queryset = CatalogProduct.objects.all()
        if instance:
            queryset = queryset.exclude(pk=instance.pk)
        candidate = base
        counter = 1
        while queryset.filter(slug=candidate).exists():
            candidate = f'{base}-{counter}'
            counter += 1
        return candidate
