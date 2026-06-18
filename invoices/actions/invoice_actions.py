from rest_framework import status

from invoices.data import InvoiceRepository
from invoices.helpers import user_can_access_invoice
from invoices.serializers import InvoiceSerializer
from invoices.utils import generate_pdf_invoice
from orders.data.order_repo import OrderRepository


class GenerateInvoiceAction:
    def execute(self, user, payload: dict):
        data = payload.copy()

        if getattr(user, 'role', '') != 'admin' and not user.is_superuser:
            validation_error = self._apply_non_admin_scope(user, data)
            if validation_error:
                response_status = validation_error.pop('status')
                return None, validation_error, response_status

        serializer = InvoiceSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()

        updated_invoice = generate_pdf_invoice(invoice.id)
        if not updated_invoice:
            return None, {'error': 'Failed to generate PDF'}, status.HTTP_500_INTERNAL_SERVER_ERROR

        return updated_invoice, None, status.HTTP_201_CREATED

    def _apply_non_admin_scope(self, user, data: dict):
        invoice_type = data.get('invoice_type')
        if invoice_type == 'vendor_settlement' and hasattr(user, 'vendor_profile'):
            data.setdefault('vendor', str(user.vendor_profile.id))
            return None

        order_id = data.get('order')
        if not order_id:
            return {'error': 'order is required.', 'status': status.HTTP_400_BAD_REQUEST}

        order = OrderRepository.get_by_id_or_none(
            order_id,
            select_related=['vendor', 'customer'],
        )
        if not order:
            return {'error': 'Order not found.', 'status': status.HTTP_404_NOT_FOUND}

        if hasattr(user, 'vendor_profile') and order.vendor == user.vendor_profile:
            data.setdefault('vendor', str(user.vendor_profile.id))
            return None
        if order.customer == user:
            data.setdefault('recipient', str(user.id))
            data.setdefault('vendor', str(order.vendor.id))
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
