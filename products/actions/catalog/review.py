from django.utils import timezone

from products.actions.approval import ProductApprovalPolicy
from products.models import Product


class ReviewVendorProductAction:
    def approve(self, admin_user, product):
        product.approval_status = Product.APPROVAL_STATUS_APPROVED
        product.rejection_reason = ''
        product.reviewed_by = admin_user
        product.reviewed_at = timezone.now()
        product.approval_change_summary = []
        ProductApprovalPolicy.ensure_catalog_for_sellable_state(product)
        product.save(update_fields=['approval_status', 'rejection_reason', 'reviewed_by', 'reviewed_at', 'approval_change_summary'])
        return product

    def reject(self, admin_user, product, reason):
        if not reason.strip():
            raise ValueError('Rejection reason is required.')
        product.approval_status = Product.APPROVAL_STATUS_REJECTED
        product.rejection_reason = reason.strip()
        product.reviewed_by = admin_user
        product.reviewed_at = timezone.now()
        product.save(update_fields=['approval_status', 'rejection_reason', 'reviewed_by', 'reviewed_at'])
        return product
