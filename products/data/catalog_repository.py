from django.db.models import Count, Exists, OuterRef, Q

from products.models import CatalogProduct, CatalogProposal, CatalogProposalItem, VendorCatalogGrant
from vendors.data.base import BaseRepository


class CatalogProductRepository(BaseRepository):
    def __init__(self):
        super().__init__(model=CatalogProduct)

    def available_for_vendor(self, vendor, search=None, catalog_id=None):
        existing_listing = vendor.products.filter(catalog_product_id=OuterRef("pk"))
        queryset = (
            CatalogProduct.objects.filter(is_active=True, vendor_grants__vendor=vendor)
            .annotate(already_added=Exists(existing_listing))
            .filter(already_added=False)
            .select_related("category")
            .prefetch_related("images")
            .distinct()
            .order_by("name")
        )
        if catalog_id:
            queryset = queryset.filter(pk=catalog_id)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(brand__icontains=search) | Q(barcode__icontains=search) | Q(search_keywords__icontains=search) | Q(category__name__icontains=search))
        return queryset



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

    def list_for_vendor(self, vendor, params=None):
        query = (
            CatalogProposal.objects.filter(vendor=vendor)
            .select_related("vendor", "reviewed_by")
            .prefetch_related("items__category", "items__created_catalog_product")
            .order_by("-submitted_at")
        )

        params = params or {}
        if params.get('status'):
            query = query.filter(status=params['status'])
        if params.get('search'):
            term = params['search']
            query = query.filter(Q(items__name__icontains=term) | Q(items__brand__icontains=term) | Q(items__barcode__icontains=term)).distinct()
        return query.order_by('-submitted_at', 'id')

    def create_with_items(self, vendor, items):
        proposal = self.create(vendor=vendor)
        for item in items:
            CatalogProposalItem.objects.create(proposal=proposal, **item)
        return proposal
