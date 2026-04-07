"""Service layer for the vendors app.

Handles KYC review, vendor status changes, document verification, and the
shared audit-log helper used by both services and views.
"""

from django.db import transaction
from django.utils import timezone

from vendors.models import Vendor, VendorDocument, VendorOnboarding, VendorAuditLog
from backend.events import vendor_approved


class VendorService:
    """Stateless service class for vendor-related business operations."""

    @staticmethod
    def get_vendor_or_none(pk) -> Vendor | None:
        """Fetch a vendor by primary key with user select_related, or None.

        Args:
            pk: The UUID primary key of the vendor.

        Returns:
            The ``Vendor`` instance with ``user`` pre-fetched, or ``None`` if
            it does not exist.
        """
        try:
            return Vendor.objects.select_related("user").get(pk=pk)
        except Vendor.DoesNotExist:
            return None

    @staticmethod
    def _create_audit_log(
        vendor: Vendor,
        action: str,
        description: str,
        request=None,
        metadata=None,
    ) -> None:
        """Record an entry in the vendor audit log.

        Extracts the requester's IP address from the request object when
        available, and writes a ``VendorAuditLog`` row.

        Args:
            vendor: The vendor the action relates to.
            action: Short machine-readable action code (e.g. ``'kyc_approved'``).
            description: Human-readable description of what happened.
            request: Optional Django/DRF request for IP and user extraction.
            metadata: Optional JSON-serialisable dict of extra context.
        """
        ip = None
        if request:
            x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
            ip = (
                x_forwarded.split(",")[0]
                if x_forwarded
                else request.META.get("REMOTE_ADDR")
            )
        VendorAuditLog.objects.create(
            vendor=vendor,
            action=action,
            description=description,
            performed_by=request.user if request else None,
            ip_address=ip,
            metadata=metadata,
        )

    @staticmethod
    @transaction.atomic
    def review_vendor_kyc(
        vendor_id: str,
        action: str,
        reason: str,
        user,
        request=None,
    ) -> VendorOnboarding:
        """Approve or reject a vendor's KYC submission.

        On approval the vendor's status is set to ``'approved'`` and the
        ``vendor_approved`` signal is emitted.  On rejection the reason is
        recorded and the status is set to ``'rejected'``.

        Args:
            vendor_id: UUID primary key of the vendor.
            action: Either ``'approve'`` or ``'reject'``.
            reason: Rejection reason (required when ``action == 'reject'``).
            user: The admin user performing the review.
            request: Optional DRF request for audit-log enrichment.

        Returns:
            The updated ``VendorOnboarding`` instance.

        Raises:
            ValueError: If the vendor is not found, ``action`` is invalid,
                or a rejection reason is missing.
        """
        try:
            vendor = Vendor.objects.select_related("user").get(pk=vendor_id)
        except Vendor.DoesNotExist:
            raise ValueError("Vendor not found.")

        allowed = ("approve", "reject")
        if action not in allowed:
            raise ValueError(f"action must be one of: {', '.join(allowed)}")
        if action == "reject" and not reason.strip():
            raise ValueError("rejection_reason is required when rejecting.")

        onboarding, _ = VendorOnboarding.objects.get_or_create(vendor=vendor)

        if action == "approve":
            onboarding.kyc_status = "verified"
            onboarding.onboarding_status = "approved"
            onboarding.rejection_reason = ""
            vendor.status = "approved"
            vendor.save(update_fields=["status"])
            audit_action = "kyc_approved"
            audit_description = "KYC verified and vendor account approved."
            vendor_approved.send(sender=Vendor, vendor=vendor)
        else:
            onboarding.kyc_status = "rejected"
            onboarding.onboarding_status = "rejected"
            onboarding.rejection_reason = reason
            vendor.status = "rejected"
            vendor.save(update_fields=["status"])
            audit_action = "kyc_rejected"
            audit_description = f"KYC rejected: {reason}"

        onboarding.reviewed_at = timezone.now()
        onboarding.reviewed_by = user
        onboarding.save()
        VendorService._create_audit_log(vendor, audit_action, audit_description, request)

        return onboarding

    @staticmethod
    @transaction.atomic
    def update_vendor_status(vendor_id: str, new_status: str) -> Vendor:
        """Change the approval/suspension status of a vendor.

        Args:
            vendor_id: UUID primary key of the vendor.
            new_status: Target status; must be one of ``pending``,
                ``approved``, ``rejected``, or ``suspended``.

        Returns:
            The updated ``Vendor`` instance.

        Raises:
            ValueError: If the vendor is not found or ``new_status`` is invalid.
        """
        try:
            vendor = Vendor.objects.get(pk=vendor_id)
        except Vendor.DoesNotExist:
            raise ValueError("Vendor not found.")

        allowed = ["pending", "approved", "rejected", "suspended"]
        if new_status not in allowed:
            raise ValueError(f"status must be one of: {', '.join(allowed)}")

        vendor.status = new_status
        vendor.save(update_fields=["status"])

        if new_status == "approved":
            vendor_approved.send(sender=Vendor, vendor=vendor)

        return vendor

    @staticmethod
    @transaction.atomic
    def verify_document(
        vendor_id: str,
        doc_id: str,
        action: str,
        reason: str,
        user,
        request=None,
    ) -> VendorDocument:
        """Verify or reject a vendor's uploaded document.

        Args:
            vendor_id: UUID primary key of the vendor.
            doc_id: UUID primary key of the ``VendorDocument``.
            action: ``'verify'`` to approve or any other value to reject.
            reason: Rejection reason (used when action is not ``'verify'``).
            user: The admin user performing the action.
            request: Optional DRF request for audit-log enrichment.

        Returns:
            The updated ``VendorDocument`` instance.

        Raises:
            ValueError: If the vendor or document is not found.
        """
        try:
            vendor = Vendor.objects.get(pk=vendor_id)
        except Vendor.DoesNotExist:
            raise ValueError("Vendor not found.")

        try:
            vendor_document = VendorDocument.objects.get(
                pk=doc_id, vendor=vendor
            )
        except VendorDocument.DoesNotExist:
            raise ValueError("Document not found.")

        if action == "verify":
            vendor_document.status = "verified"
            vendor_document.rejection_reason = ""
            vendor_document.verified_by = user
            vendor_document.verified_at = timezone.now()
            audit_action = "document_verified"
            audit_description = (
                f"Document verified: "
                f"{vendor_document.get_document_type_display()}"
            )
        else:
            vendor_document.status = "rejected"
            vendor_document.rejection_reason = reason
            vendor_document.verified_by = user
            vendor_document.verified_at = timezone.now()
            audit_action = "document_rejected"
            audit_description = (
                f"Document rejected: "
                f"{vendor_document.get_document_type_display()} - {reason}"
            )

        vendor_document.save()
        VendorService._create_audit_log(
            vendor, audit_action, audit_description, request
        )
        return vendor_document
