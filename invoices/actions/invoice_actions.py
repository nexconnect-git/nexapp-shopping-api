from rest_framework import status
from accounts.admin_access import allows
from uuid import UUID
from rest_framework.exceptions import NotFound

from invoices.data import InvoiceRepository
from invoices.helpers import user_can_access_invoice
from invoices.serializers import InvoiceSerializer
from invoices.utils import generate_pdf_invoice
from orders.data.order_repo import OrderRepository
from vendors.data.payout_repository import PayoutRepository


class GenerateInvoiceAction:
    def execute(self, user, payload: dict):
        data = payload.copy()

        if getattr(user, 'role', '') == 'admin' and not allows(user, 'finance.manage'):
            return None, {'error': 'Finance management permission is required.'}, status.HTTP_403_FORBIDDEN

        validation_error = self._apply_record_scope(user, data)
        if validation_error:
            response_status = validation_error.pop('status')
            return None, validation_error, response_status

        serializer = InvoiceSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        invoice = InvoiceRepository.create(**serializer.validated_data)

        updated_invoice = generate_pdf_invoice(invoice.id)
        if not updated_invoice:
            InvoiceRepository.delete(invoice)
            return None, {'error': 'Failed to generate PDF'}, status.HTTP_500_INTERNAL_SERVER_ERROR

        return updated_invoice, None, status.HTTP_201_CREATED

    def _apply_record_scope(self, user, data: dict):
        invoice_type = data.get('invoice_type')
        is_admin = getattr(user, 'role', '') == 'admin'
        if invoice_type in ('vendor_settlement', 'delivery_payout'):
            try:
                payout_id = UUID(str(data.pop('payout_id', '')))
            except (ValueError, TypeError):
                return {'error': 'A valid payout_id is required.', 'status': status.HTTP_400_BAD_REQUEST}
            kind = 'vendor' if invoice_type == 'vendor_settlement' else 'delivery'
            try:
                payout = PayoutRepository(kind).detail(payout_id)
            except NotFound:
                return {'error': 'Payout not found.', 'status': status.HTTP_404_NOT_FOUND}
            owner_id = payout.vendor.user_id if kind == 'vendor' else payout.delivery_partner_id
            if not is_admin and owner_id != user.pk:
                return {'error': 'You do not have access to this payout.', 'status': status.HTTP_403_FORBIDDEN}
            data.update(order=None, vendor=str(payout.vendor_id) if kind == 'vendor' else None,
                        recipient=str(owner_id), amount=str(payout.net_payout if kind == 'vendor' else payout.total_earnings), tax_amount='0.00',
                        notes=f'Payout {payout.pk}; period {payout.period_start.isoformat()} to {payout.period_end.isoformat()}; recorded status: {payout.status}. This document does not independently verify a bank transfer.')
            return None

        order_id = data.get('order')
        if not order_id:
            return {'error': 'order is required.', 'status': status.HTTP_400_BAD_REQUEST}

        try:
            order_id = UUID(str(order_id))
        except (ValueError, TypeError):
            return {'error': 'A valid order is required.', 'status': status.HTTP_400_BAD_REQUEST}
        order = OrderRepository.get_by_id_or_none(
            order_id,
            select_related=['vendor', 'customer'],
        )
        if not order:
            return {'error': 'Order not found.', 'status': status.HTTP_404_NOT_FOUND}

        if is_admin or order.customer_id == user.pk or order.vendor.user_id == user.pk:
            data.update(vendor=str(order.vendor_id), recipient=str(order.customer_id), amount=str(order.total), tax_amount=str(order.tax_amount))
            return None

        return {
            'error': 'You do not have permission to generate an invoice for this order.',
            'status': status.HTTP_403_FORBIDDEN,
        }


class GetInvoiceDownloadAction:
    def __init__(self, repository: InvoiceRepository = None):
        self.repository = repository or InvoiceRepository()

    def execute(self, user, invoice_id):
        invoice = self.repository.get_by_id_with_related(invoice_id)
        if not invoice:
            return None, {'error': 'Invoice not found.'}, status.HTTP_404_NOT_FOUND
        if not user_can_access_invoice(user, invoice):
            return None, {'error': 'Unauthorized'}, status.HTTP_403_FORBIDDEN
        if not invoice.pdf_file:
            return None, {'error': 'PDF not generated yet.'}, status.HTTP_404_NOT_FOUND
        return invoice, None, status.HTTP_200_OK
