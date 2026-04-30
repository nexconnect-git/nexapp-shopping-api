from django.db.models import Exists, OuterRef

from products.models import CatalogProduct, CatalogProposal, VendorCatalogGrant
from vendors.data.base import BaseRepository


class CatalogProductRepository(BaseRepository):
    def __init__(self):
        super().__init__(model=CatalogProduct)

    def available_for_vendor(self, vendor):
        existing_listing = vendor.products.filter(catalog_product_id=OuterRef("pk"))
        return (
            CatalogProduct.objects.filter(is_active=True, vendor_grants__vendor=vendor)
            .annotate(already_added=Exists(existing_listing))
            .filter(already_added=False)
            .select_related("category")
            .prefetch_related("images")
            .distinct()
            .order_by("name")
        )


class VendorCatalogGrantRepository(BaseRepository):
    def __init__(self):
        super().__init__(model=VendorCatalogGrant)

    def has_grant(self, vendor, catalog_product):
        return VendorCatalogGrant.objects.filter(
            vendor=vendor,
            catalog_product=catalog_product,
        ).exists()

    def grant(self, vendor, catalog_product, granted_by=None):
        return VendorCatalogGrant.objects.get_or_create(
            vendor=vendor,
            catalog_product=catalog_product,
            defaults={"granted_by": granted_by},
        )[0]


class CatalogProposalRepository(BaseRepository):
    def __init__(self):
        super().__init__(model=CatalogProposal)

    def list_for_admin(self):
        return (
            CatalogProposal.objects.select_related("vendor", "reviewed_by")
            .prefetch_related("items__category", "items__created_catalog_product")
            .order_by("-submitted_at")
        )

    def list_for_vendor(self, vendor):
        return (
            CatalogProposal.objects.filter(vendor=vendor)
            .select_related("vendor", "reviewed_by")
            .prefetch_related("items__category", "items__created_catalog_product")
            .order_by("-submitted_at")
        )
