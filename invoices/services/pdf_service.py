"""
PDFService — encapsulates xhtml2pdf-based PDF generation for invoices.
"""
import io
from django.core.files.base import ContentFile
from django.template.loader import get_template
from xhtml2pdf import pisa


_TEMPLATE_MAP = {
    'vendor_settlement': 'invoices/vendor_settlement.html',
}
_DEFAULT_TEMPLATE = 'invoices/customer_invoice.html'


class PDFService:
    """Generates a PDF from an Invoice instance and saves it to the model's
    ``pdf_file`` field."""

    def generate_for_invoice(self, invoice) -> bool:
        """Render the appropriate HTML template to PDF and attach it to the
        invoice.

        Returns:
            True if the PDF was successfully generated and saved, False
            otherwise.
        """
        template_name = _TEMPLATE_MAP.get(invoice.invoice_type, _DEFAULT_TEMPLATE)
        context = {
            'invoice': invoice,
            'order': invoice.order,
            'vendor': invoice.vendor,
            'recipient': invoice.recipient,
            'items': invoice.order.items.all() if invoice.order else [],
        }

        html_content = get_template(template_name).render(context)
        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)

        if pisa_status.err:
            return False

        pdf_filename = f'{invoice.invoice_number}.pdf'
        invoice.pdf_file.save(pdf_filename, ContentFile(pdf_buffer.getvalue()), save=True)
        return True
