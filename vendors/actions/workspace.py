from datetime import time

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.actions.audit_actions import CreateAdminAuditLogAction
from helpers.vendor_hours import get_vendor_availability, is_vendor_within_hours
from support.actions import CreateTicketAction
from vendors.data.workspace_repository import VendorWorkspaceRepository
from vendors.serializers.public import VendorSerializer
from vendors.serializers.workspace import OwnerVendorProfileSerializer


class GetVendorWorkspaceAction:
    def execute(self, vendor):
        repository = VendorWorkspaceRepository()
        inventory = repository.inventory_summary(vendor)
        blockers = []
        if vendor.status != 'approved':
            blockers.append({'code': 'approval', 'message': 'Store approval is required.', 'route': '/pending-approval'})
        if vendor.user.force_password_change:
            blockers.append({'code': 'password', 'message': 'Change your temporary password.', 'route': '/change-password'})
        if not all((vendor.store_name, vendor.phone, vendor.address, vendor.city, vendor.state, vendor.postal_code)):
            blockers.append({'code': 'profile', 'message': 'Complete your store contact and pickup address.', 'route': '/store-settings'})
        review_current = bool(vendor.stock_reviewed_at and timezone.localtime(vendor.stock_reviewed_at).date() == timezone.localdate() and (inventory['updated_at'] is None or inventory['updated_at'] <= vendor.stock_reviewed_at))
        if vendor.require_stock_check and not review_current:
            blockers.append({'code': 'stock_review', 'message': 'Review current inventory before opening or enabling intake.', 'route': '/inventory'})
        available, availability_note = get_vendor_availability(vendor)
        within_hours = is_vendor_within_hours(vendor)
        if vendor.status != 'approved' or vendor.user.force_password_change:
            code, label, reason = 'blocked', 'Store access blocked', blockers[0]['message']
        elif not vendor.is_open:
            code, label, reason = 'closed', 'Store closed', 'The store switch is off.'
        elif not vendor.is_accepting_orders:
            code, label, reason = 'paused', 'Orders paused', 'New order intake is paused.'
        elif not within_hours:
            code, label, reason = 'outside_hours', 'Outside opening hours', availability_note
        elif available:
            code, label, reason = 'receiving', 'Receiving orders', availability_note
        else:
            code, label, reason = 'unavailable', 'Store unavailable', availability_note
        return {
            'vendor': VendorSerializer(vendor).data,
            'operating': {'is_open': vendor.is_open, 'is_accepting_orders': vendor.is_accepting_orders, 'is_open_now': available, 'is_within_hours': within_hours, 'availability_note': availability_note, 'effective_status': {'code': code, 'label': label, 'reason': reason}},
            'readiness': {'blockers': blockers, 'can_open': not blockers, 'can_enable_intake': not blockers, 'stock_review_required': vendor.require_stock_check, 'stock_review_current': review_current},
            'inventory': inventory,
            'verification': repository.verification_summary(vendor),
            'allowed_actions': {'operate': vendor.status == 'approved' and not vendor.user.force_password_change, 'correct_details': vendor.status in ('pending_details', 'invalid_details'), 'upload_documents': vendor.status in ('pending_documents', 'invalid_documents'), 'contact': True},
            'timezone': timezone.get_current_timezone_name(),
            'updated_at': timezone.now(),
        }


class UpdateOwnerVendorProfileAction:
    @transaction.atomic
    def execute(self, vendor, data, request):
        repository = VendorWorkspaceRepository()
        vendor = repository.locked(vendor)
        if vendor.status != 'approved' and vendor.status not in ('pending_details', 'invalid_details'):
            raise PermissionDenied('Profile corrections are available only when requested by the platform.')
        if vendor.user.force_password_change:
            raise PermissionDenied('Change your temporary password first.')
        allowed_corrections = {'store_name', 'description', 'logo', 'banner', 'phone', 'email', 'address', 'city', 'state', 'postal_code', 'latitude', 'longitude'}
        if vendor.status != 'approved' and set(data) - allowed_corrections:
            raise PermissionDenied('Operating settings cannot be changed before approval.')
        serializer = OwnerVendorProfileSerializer(vendor, data=data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        repository.save(vendor, serializer.validated_data)
        CreateAdminAuditLogAction().execute(request=request, action='update', entity_type='vendor', entity_id=str(vendor.pk), summary='Vendor updated own business profile.', metadata={'fields': sorted(data)})
        return vendor


class UpdateVendorOperatingStateAction:
    @transaction.atomic
    def execute(self, vendor, values, request=None):
        repository = VendorWorkspaceRepository()
        vendor = repository.locked(vendor)
        if vendor.status != 'approved' or vendor.user.force_password_change:
            raise PermissionDenied('Approved vendor access and completed account security are required.')
        if values.get('is_open') or values.get('is_accepting_orders'):
            context = GetVendorWorkspaceAction().execute(vendor)
            if context['readiness']['blockers']:
                raise ValidationError({'detail': 'Resolve store readiness blockers.', 'blockers': context['readiness']['blockers']})
        repository.save(vendor, values)
        CreateAdminAuditLogAction().execute(request=request, actor=vendor.user, action='update', entity_type='vendor', entity_id=str(vendor.pk), summary='Vendor changed store operating state.', metadata={key: str(value) if isinstance(value, time) else value for key, value in values.items()})
        return vendor


class ReviewVendorInventoryAction:
    @transaction.atomic
    def execute(self, vendor, values):
        repository = VendorWorkspaceRepository()
        vendor = repository.locked(vendor)
        inventory = repository.inventory_summary(vendor)
        if not values['confirmed'] or values['product_count'] != inventory['total'] or values['updated_at'] != inventory['updated_at']:
            raise ValidationError('Inventory changed since this review. Refresh and review again.')
        repository.mark_stock_reviewed(vendor)
        return GetVendorWorkspaceAction().execute(vendor)


class UploadOwnVendorDocumentAction:
    def execute(self, vendor, values):
        if vendor.status not in ('pending_documents', 'invalid_documents'):
            raise PermissionDenied('Document correction is not currently requested.')
        return VendorWorkspaceRepository().create_document(vendor, values)


class ContactVendorOnboardingAction:
    def execute(self, vendor, values):
        return CreateTicketAction().execute(vendor=vendor, validated_data={**values, 'category': 'account'})
