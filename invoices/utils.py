from invoices.data import InvoiceRepository
from invoices.services.pdf_service import PDFService


def generate_pdf_invoice(invoice_id):
    invoice = InvoiceRepository.get_by_id_with_related(invoice_id)
    if not invoice:
        return None
    return invoice if PDFService().generate_for_invoice(invoice) else None
