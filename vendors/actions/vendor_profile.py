from django.db import transaction
from rest_framework.exceptions import NotFound

from accounts.actions.audit_actions import CreateAdminAuditLogAction
from vendors.actions.vendor_metadata import UpdateVendorMetadataAction
from vendors.data.vendor_metadata_repository import VendorMetadataRepository, ONBOARD_FIELDS, BANK_FIELDS
from vendors.serializers.admin import AdminVendorSerializer


class UpdateAdminVendorProfileAction:
    @transaction.atomic
    def execute(self, vendor_id, data, request):
        vendor = VendorMetadataRepository().locked(vendor_id)
        if not vendor:
            raise NotFound('Vendor not found.')
        serializer = AdminVendorSerializer(vendor, data=data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        metadata = {key: values.pop(key) for key in ONBOARD_FIELDS + BANK_FIELDS + ('serviceable_pincodes', 'holidays') if key in values}
        UpdateVendorMetadataAction().execute(vendor, metadata)
        serializer.save()
        CreateAdminAuditLogAction().execute(request=request, action='update', entity_type='vendor', entity_id=str(vendor.pk), summary='Updated vendor profile.', metadata={'fields': sorted(set(data))})
        return AdminVendorSerializer(vendor, context={'request': request}).data
