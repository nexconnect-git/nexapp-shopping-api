from django.db import transaction
from django.utils import timezone

from notifications.models import Notification
from products.actions.catalog.slug import CatalogSlugMixin
from products.data.catalog_repository import VendorCatalogGrantRepository
from products.models import CatalogProduct, CatalogProposal, CatalogProposalItem


class CreateCatalogProposalAction:
    def execute(self, vendor, items):
        if not items:
            raise ValueError('At least one proposed item is required.')
        with transaction.atomic():
            proposal = CatalogProposal.objects.create(vendor=vendor)
            for item in items:
                CatalogProposalItem.objects.create(
                    proposal=proposal,
                    name=item['name'],
                    category=item.get('category'),
                    description=item.get('description', ''),
                    brand=item.get('brand', ''),
                    unit=item.get('unit', 'piece'),
                    barcode=item.get('barcode', ''),
                    sku_hint=item.get('sku_hint', ''),
                )
            return proposal


class ProposalStatusMixin:
    def refresh_proposal(self, proposal, admin_user, admin_notes):
        statuses = list(proposal.items.values_list('status', flat=True))
        if all(item_status == 'approved' for item_status in statuses):
            proposal.status = 'approved'
        elif all(item_status == 'rejected' for item_status in statuses):
            proposal.status = 'rejected'
        elif any(item_status in ('approved', 'rejected') for item_status in statuses):
            proposal.status = 'partially_approved'
        proposal.reviewed_by = admin_user
        proposal.reviewed_at = timezone.now()
        if admin_notes:
            proposal.admin_notes = admin_notes
        proposal.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'admin_notes'])


class ApproveCatalogProposalItemAction(CatalogSlugMixin, ProposalStatusMixin):
    def execute(self, proposal_id, item_id, admin_user, catalog_product_id=None, admin_notes=''):
        proposal = CatalogProposal.objects.select_related('vendor__user').get(pk=proposal_id)
        item = proposal.items.select_related('category').get(pk=item_id)
        if item.status != 'pending':
            raise ValueError('Only pending proposal items can be approved.')

        with transaction.atomic():
            catalog_product = self._catalog_product(item, admin_user, catalog_product_id)
            VendorCatalogGrantRepository().grant(proposal.vendor, catalog_product, admin_user)
            item.status = 'approved'
            item.created_catalog_product = catalog_product
            item.reviewed_at = timezone.now()
            item.save(update_fields=['status', 'created_catalog_product', 'reviewed_at'])
            self.refresh_proposal(proposal, admin_user, admin_notes)
            Notification.objects.create(
                user=proposal.vendor.user,
                title='Catalog item approved',
                message=f'{catalog_product.name} is approved for your store catalog.',
                notification_type='system',
                data={
                    'proposal_id': str(proposal.id),
                    'proposal_item_id': str(item.id),
                    'catalog_product_id': str(catalog_product.id),
                },
            )
            return item

    def _catalog_product(self, item, admin_user, catalog_product_id=None):
        if catalog_product_id:
            return CatalogProduct.objects.get(pk=catalog_product_id)
        return CatalogProduct.objects.create(
            category=item.category,
            name=item.name,
            slug=self.unique_catalog_slug(item.name),
            description=item.description,
            brand=item.brand,
            unit=item.unit or 'piece',
            barcode=item.barcode,
            created_by=admin_user,
        )


class RejectCatalogProposalItemAction(ProposalStatusMixin):
    def execute(self, proposal_id, item_id, admin_user, rejection_reason='', admin_notes=''):
        proposal = CatalogProposal.objects.select_related('vendor__user').get(pk=proposal_id)
        item = proposal.items.get(pk=item_id)
        if item.status != 'pending':
            raise ValueError('Only pending proposal items can be rejected.')

        with transaction.atomic():
            item.status = 'rejected'
            item.rejection_reason = rejection_reason
            item.reviewed_at = timezone.now()
            item.save(update_fields=['status', 'rejection_reason', 'reviewed_at'])
            self.refresh_proposal(proposal, admin_user, admin_notes)
            Notification.objects.create(
                user=proposal.vendor.user,
                title='Catalog item rejected',
                message=rejection_reason or f'{item.name} was not approved for the catalog.',
                notification_type='system',
                data={
                    'proposal_id': str(proposal.id),
                    'proposal_item_id': str(item.id),
                },
            )
            return item
