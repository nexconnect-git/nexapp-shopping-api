from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.actions.audit_actions import CreateAdminAuditLogAction
from backend.data.admin_console_repository import AdminConsoleRepository
from orders.data.operations_repo import RefundLedgerRepository


class MutateRefundLedgerAction:
    """Record requests and verified external evidence; never simulate a transfer."""
    transitions = {
        'requested': {'approved', 'cancelled'},
        'approved': {'processing', 'cancelled'},
        'processing': {'processed', 'failed'},
        'failed': {'processing', 'cancelled'},
        'processed': set(), 'cancelled': set(),
    }

    @transaction.atomic
    def execute(self, data, request, pk=None):
        repository = RefundLedgerRepository()
        existing = repository.locked(pk) if pk else None
        order_id = existing.order_id if existing else data['order'].pk
        order = AdminConsoleRepository.locked_order(order_id)
        if existing and any(key in data and data[key] != getattr(existing, key) for key in ('order', 'customer', 'issue', 'amount', 'method')):
            raise ValidationError('Refund identity, amount and method cannot be changed. Cancel and create a corrected request.')
        if existing and existing.status in ('processed', 'cancelled'):
            raise ValidationError('Terminal refund records are immutable.')
        customer = data.get('customer') or order.customer
        issue = data.get('issue')
        if customer.pk != order.customer_id or (issue and issue.order_id != order.pk):
            raise ValidationError('Customer and issue must belong to the refund order.')
        amount = data.get('amount', existing.amount if existing else Decimal('0'))
        if amount <= 0 or amount > order.total:
            raise ValidationError({'amount': 'Amount must be positive and cannot exceed the order total.'})
        if repository.reserved_amount(order.pk, existing.pk if existing else None) + amount > order.total:
            raise ValidationError({'amount': 'Combined outstanding and processed refunds exceed the order total.'})
        reason = data.get('reason', existing.reason if existing else '').strip()
        if not reason:
            raise ValidationError({'reason': 'A refund reason is required.'})
        next_status = data.get('status', existing.status if existing else 'requested')
        if not existing and next_status != 'requested':
            raise ValidationError({'status': 'New refunds must begin as requested.'})
        if existing and next_status != existing.status and next_status not in self.transitions[existing.status]:
            raise ValidationError({'status': 'Invalid refund state transition.'})
        if next_status == 'processed':
            if existing.method == 'wallet':
                raise ValidationError('Wallet credits must be processed by the wallet refund workflow, not entered as an external transfer.')
            if not data.get('gateway_refund_id', existing.gateway_refund_id).strip():
                raise ValidationError({'gateway_refund_id': 'An external refund or transfer reference is required.'})
        if next_status == 'failed' and not data.get('failure_reason', existing.failure_reason).strip():
            raise ValidationError({'failure_reason': 'A failure reason is required.'})
        previous = existing.status if existing else None
        values = {**data, 'reason': reason}
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
            if next_status == 'approved' and not existing.approved_at:
                existing.approved_by, existing.approved_at = request.user, timezone.now()
            if next_status == 'processed':
                existing.processed_by, existing.processed_at = request.user, timezone.now()
            refund = repository.save(existing)
        else:
            refund = repository.create(**values, customer=customer, requested_by=request.user) if 'customer' not in values else repository.create(**values, requested_by=request.user)
        CreateAdminAuditLogAction().execute(request=request, action='refund_update' if existing else 'refund_create', entity_type='refund_ledger', entity_id=str(refund.pk), summary=f'Recorded refund {refund.status} for {order.order_number}.', metadata={'order_id': str(order.pk), 'old_status': previous, 'new_status': refund.status, 'amount': str(refund.amount), 'method': refund.method, 'reference': refund.gateway_refund_id, 'reason': reason})
        return refund
