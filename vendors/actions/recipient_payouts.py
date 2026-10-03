from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from accounts.actions.audit_actions import CreateAdminAuditLogAction
from vendors.data.payout_repository import PayoutRepository


class UpdateVendorRecipientPayoutAction:
    @transaction.atomic
    def execute(self, payout_id, operation, request):
        repository = PayoutRepository('vendor')
        payout = repository.locked(payout_id)
        if request.user.role != 'vendor' or repository.recipient_user_id(payout) != request.user.pk:
            raise NotFound('Payout not found.')
        expected = 'paid' if operation == 'verify' else 'pending_approval'
        if payout.status != expected:
            raise ValidationError({'detail': 'This payout changed. Refresh before continuing.', 'status': payout.status})
        previous = payout.status
        if operation == 'approve':
            payout.status = 'approved'
            payout.vendor_approved_at = timezone.now()
            payout.vendor_rejection_reason = ''
            fields = ['status', 'vendor_approved_at', 'vendor_rejection_reason']
        elif operation == 'decline':
            reason = request.data.get('reason')
            if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
                raise ValidationError({'reason': 'Enter a reason of at most 500 characters.'})
            payout.status = 'failed'
            payout.vendor_rejection_reason = reason.strip()
            fields = ['status', 'vendor_rejection_reason']
        elif operation == 'verify':
            payout.status = 'verified'
            payout.vendor_verified_at = timezone.now()
            fields = ['status', 'vendor_verified_at']
        else:
            raise ValidationError('Unsupported payout action.')
        payout.save(update_fields=fields)
        CreateAdminAuditLogAction().execute(request=request, action='payout', entity_type='vendor_payout', entity_id=str(payout.pk), summary=f'Vendor {operation} payout.', metadata={'previous_status': previous, 'status': payout.status})
        return payout
