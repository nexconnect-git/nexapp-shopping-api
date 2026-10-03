from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from accounts.actions.audit_actions import CreateAdminAuditLogAction
from notifications.data.notification_repository import NotificationRepository
from vendors.actions.wallet_actions import VendorWalletAction
from vendors.data.payout_repository import PayoutRepository
from vendors.serializers import DeliveryPartnerPayoutSerializer, VendorPayoutSerializer


class UpdateAdminPayoutAction:
    @transaction.atomic
    def execute(self, kind, payout_id, operation, data, request=None):
        payout = PayoutRepository(kind).locked(payout_id)
        serializer_class = VendorPayoutSerializer if kind == 'vendor' else DeliveryPartnerPayoutSerializer
        previous_status = payout.status
        if operation == 'record_payment':
            reference = str(data.get('transaction_ref') or '').strip()
            if not reference or len(reference) > 100:
                raise ValidationError({'transaction_ref': 'An external payment reference of at most 100 characters is required.'})
            if payout.status in ('paid', 'verified'):
                if payout.transaction_ref == reference:
                    return payout
                raise ValidationError('This payout already has a different payment reference.')
            if payout.status not in ('approved', 'scheduled'):
                raise ValidationError('The recipient must approve the payout before recording payment.')
            amount = payout.net_payout if kind == 'vendor' else payout.total_earnings
            if amount <= 0:
                raise ValidationError('The payout amount must be positive.')
            if kind == 'vendor':
                try:
                    VendorWalletAction.debit_vendor(str(payout.vendor_id), amount, 'payout_withdrawal', str(payout.pk), 'External payout recorded')
                except ValueError as exc:
                    raise ValidationError(str(exc))
            payout.transaction_ref = reference
            payout.status = 'paid'
            payout.paid_at = payout.payment_sent_at = timezone.now()
            payout.save(update_fields=['transaction_ref', 'status', 'paid_at', 'payment_sent_at'])
            NotificationRepository().create(user_id=PayoutRepository(kind).recipient_user_id(payout), title='Payout payment recorded', message='An external payment reference has been recorded. Check your bank credit before verifying this payout.', notification_type='payout', data={'payout_id': str(payout.pk)})
        elif operation == 'schedule':
            if payout.status not in ('approved', 'scheduled'):
                raise ValidationError('Only recipient-approved payouts can be scheduled.')
            payout.status = 'scheduled'
            payout.save(update_fields=['status'])
        elif operation == 'verify_override':
            reason = str(data.get('reason') or '').strip()
            if not reason:
                raise ValidationError({'reason': 'Explain why recipient verification is being overridden.'})
            if payout.status != 'paid' or not payout.transaction_ref or not payout.payment_sent_at or timezone.now() - payout.payment_sent_at < timedelta(hours=48):
                raise ValidationError('An evidenced payment must remain unverified for 48 hours before an override.')
            verified_field = 'vendor_verified_at' if kind == 'vendor' else 'partner_verified_at'
            payout.status = 'verified'
            setattr(payout, verified_field, timezone.now())
            payout.save(update_fields=['status', verified_field])
        elif operation == 'edit':
            allowed = {'period_start', 'period_end', 'gross_sales', 'platform_commission', 'net_payout'} if kind == 'vendor' else {'period_start', 'period_end', 'total_deliveries', 'total_earnings'}
            if set(data) - allowed or payout.status != 'pending_approval':
                raise ValidationError('Only amounts and period fields of an unapproved payout can be edited.')
            serializer = serializer_class(payout, data=data, partial=True)
            serializer.is_valid(raise_exception=True)
            values = serializer.validated_data
            start, end = values.get('period_start', payout.period_start), values.get('period_end', payout.period_end)
            if start > end or any(value < 0 for key, value in values.items() if key not in ('period_start', 'period_end')):
                raise ValidationError('Use a valid period and non-negative amounts.')
            if kind == 'vendor' and values.get('net_payout', payout.net_payout) != values.get('gross_sales', payout.gross_sales) - values.get('platform_commission', payout.platform_commission):
                raise ValidationError('Net payout must equal gross sales minus commission.')
            serializer.save()
        else:
            raise ValidationError('Unknown payout operation.')
        CreateAdminAuditLogAction().execute(request=request, action='payout', entity_type=f'{kind}_payout', entity_id=str(payout.pk), summary=f'{operation.replace("_", " ").capitalize()} for payout {payout.pk}.', metadata={'previous_status': previous_status, 'status': payout.status, **dict(data)})
        return payout


class CreateAdminPayoutAction:
    @transaction.atomic
    def execute(self, kind, data, request):
        serializer_class = VendorPayoutSerializer if kind == 'vendor' else DeliveryPartnerPayoutSerializer
        allowed = {'vendor', 'period_start', 'period_end', 'gross_sales', 'platform_commission', 'net_payout', 'status'} if kind == 'vendor' else {'delivery_partner', 'period_start', 'period_end', 'total_deliveries', 'total_earnings', 'status'}
        if set(data) - allowed or data.get('status', 'pending_approval') != 'pending_approval':
            raise ValidationError('Create an unapproved payout with amount and period fields only.')
        serializer = serializer_class(data={**data, 'status': 'pending_approval'})
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        if values['period_start'] > values['period_end']:
            raise ValidationError('Period end must follow period start.')
        if kind == 'vendor':
            if values.get('net_payout', 0) <= 0 or values.get('platform_commission', 0) < 0 or values.get('gross_sales', 0) - values.get('platform_commission', 0) != values.get('net_payout', 0):
                raise ValidationError('A positive net payout must equal gross sales minus non-negative commission.')
        elif values['delivery_partner'].role != 'delivery' or values.get('total_earnings', 0) <= 0 or values.get('total_deliveries', 0) < 0:
            raise ValidationError('Select a delivery account with positive earnings and a valid delivery count.')
        repository = PayoutRepository(kind)
        recipient = values['vendor' if kind == 'vendor' else 'delivery_partner']
        repository.lock_recipient(recipient)
        if repository.overlaps(recipient, values['period_start'], values['period_end']):
            raise ValidationError('A payout already covers this recipient and period.')
        payout = repository.create(**values)
        CreateAdminAuditLogAction().execute(request=request, action='payout', entity_type=f'{kind}_payout', entity_id=str(payout.pk), summary='Created payout awaiting recipient approval.', metadata={'status': payout.status})
        return payout


class DeclineDeliveryPayoutAction:
    @transaction.atomic
    def execute(self, payout_id, reason, request):
        payout = PayoutRepository('delivery').locked(payout_id)
        if payout.delivery_partner_id != request.user.pk or request.user.role != 'delivery':
            raise NotFound('Payout not found.')
        if payout.status != 'pending_approval':
            raise ValidationError('Only payouts awaiting approval can be declined.')
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
            raise ValidationError('Provide a rejection reason of at most 500 characters.')
        payout.status = 'failed'
        payout.partner_rejection_reason = reason.strip()
        payout.save(update_fields=['status', 'partner_rejection_reason'])
        CreateAdminAuditLogAction().execute(request=request, action='payout', entity_type='delivery_payout', entity_id=str(payout.pk), summary='Recipient declined payout.', metadata={'reason': reason.strip()})
        return payout
