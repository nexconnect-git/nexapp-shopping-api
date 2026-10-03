from products.models import Product
from vendors.data.base import BaseRepository


class VendorInheritanceRepository(BaseRepository):
    def __init__(self):
        super().__init__(model=Product)

    def owned(self, vendor):
        return self.model.objects.filter(vendor=vendor, catalog_product__isnull=False).select_related('catalog_product', 'category', 'reviewed_by').prefetch_related('images', 'catalog_product__images').order_by('-updated_at', 'id')

    def locked(self, vendor, product_id):
        return self.owned(vendor).select_for_update(of=('self',)).filter(pk=product_id).first()

    def batch(self, vendor, batch_id):
        return self.owned(vendor).filter(submission_batch_id=batch_id)

    def selected_locked(self, vendor, ids):
        return self.owned(vendor).select_for_update(of=('self',)).filter(id__in=ids)

    def duplicate_exists(self, vendor, catalog_product, brand, quantity, unit, ignore_id=None):
        query = self.model.objects.filter(vendor=vendor, catalog_product=catalog_product, brand_normalized=brand, quantity_normalized=quantity, unit_normalized=unit)
        return query.exclude(pk=ignore_id).exists() if ignore_id else query.exists()

    def slug_exists(self, slug):
        return self.model.objects.filter(slug=slug).exists()

    def save(self, product, fields=None):
        product.save(update_fields=fields)
        return product
