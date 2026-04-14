from django.db import transaction
from django.utils import timezone
from vendors.actions.base import BaseAction

from vendors.models import Vendor, VendorDocument, VendorOnboarding, VendorAuditLog
from backend.events import vendor_approved

def _create_audit_log(vendor: Vendor, action: str, description: str, request=None, metadata=None) -> None:
    ip = None
    if request:
        x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        ip = x_forwarded.split(",")[0] if x_forwarded else request.META.get("REMOTE_ADDR")
    VendorAuditLog.objects.create(
        vendor=vendor, action=action, description=description,
        performed_by=request.user if request else None,
        ip_address=ip, metadata=metadata,
    )

class ReviewVendorKycAction(BaseAction):
    @transaction.atomic
    def execute(self, vendor_id: str, action: str, reason: str, user, request=None):
        try:
            vendor = Vendor.objects.select_related("user").get(pk=vendor_id)
        except Vendor.DoesNotExist:
            raise ValueError("Vendor not found.")

        if action not in ("approve", "reject"):
            raise ValueError("action must be one of: approve, reject")
        if action == "reject" and not reason.strip():
            raise ValueError("rejection_reason is required when rejecting.")

        onboarding, _ = VendorOnboarding.objects.get_or_create(vendor=vendor)

        if action == "approve":
            onboarding.kyc_status = "verified"
            onboarding.onboarding_status = "approved"
            onboarding.rejection_reason = ""
            vendor.status = "approved"
            vendor.save(update_fields=["status"])
            _create_audit_log(vendor, "kyc_approved", "KYC verified and vendor account approved.", request)
            vendor_approved.send(sender=Vendor, vendor=vendor)
        else:
            onboarding.kyc_status = "rejected"
            onboarding.onboarding_status = "rejected"
            onboarding.rejection_reason = reason
            vendor.status = "rejected"
            vendor.save(update_fields=["status"])
            _create_audit_log(vendor, "kyc_rejected", f"KYC rejected: {reason}", request)

        onboarding.reviewed_at = timezone.now()
        onboarding.reviewed_by = user
        onboarding.save()

        return onboarding


class UpdateVendorStatusAction(BaseAction):
    @transaction.atomic
    def execute(self, vendor_id: str, new_status: str):
        try:
            vendor = Vendor.objects.get(pk=vendor_id)
        except Vendor.DoesNotExist:
            raise ValueError("Vendor not found.")

        if new_status not in ["pending", "approved", "rejected", "suspended"]:
            raise ValueError("status must be pending, approved, rejected, or suspended")

        vendor.status = new_status
        vendor.save(update_fields=["status"])

        if new_status == "approved":
            vendor_approved.send(sender=Vendor, vendor=vendor)

        return vendor


class VerifyVendorDocumentAction(BaseAction):
    @transaction.atomic
    def execute(self, vendor_id: str, doc_id: str, action: str, reason: str, user, request=None):
        try:
            vendor = Vendor.objects.get(pk=vendor_id)
        except Vendor.DoesNotExist:
            raise ValueError("Vendor not found.")

        try:
            vendor_document = VendorDocument.objects.get(pk=doc_id, vendor=vendor)
        except VendorDocument.DoesNotExist:
            raise ValueError("Document not found.")

        if action == "verify":
            vendor_document.status = "verified"
            vendor_document.rejection_reason = ""
            vendor_document.verified_by = user
            vendor_document.verified_at = timezone.now()
            _create_audit_log(vendor, "document_verified", f"Document verified: {vendor_document.get_document_type_display()}", request)
        else:
            vendor_document.status = "rejected"
            vendor_document.rejection_reason = reason
            vendor_document.verified_by = user
            vendor_document.verified_at = timezone.now()
            _create_audit_log(vendor, "document_rejected", f"Document rejected: {vendor_document.get_document_type_display()} - {reason}", request)

        vendor_document.save()
        return vendor_document
