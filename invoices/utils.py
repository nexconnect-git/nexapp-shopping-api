import io
from django.core.files.base import ContentFile
from django.template.loader import get_template
from xhtml2pdf import pisa
from .models import Invoice

def generate_pdf_invoice(invoice_id):
    try:
        invoice = Invoice.objects.get(id=invoice_id)
    except Invoice.DoesNotExist:
        return None

    # Context for the template
    context = {
        'invoice': invoice,
        'order': invoice.order,
        'vendor': invoice.vendor,
        'recipient': invoice.recipient,
        'items': invoice.order.items.all() if invoice.order else [],
    }

    # Decide template based on invoice_type
    template_name = 'invoices/customer_invoice.html'
    if invoice.invoice_type == 'vendor_settlement':
        template_name = 'invoices/vendor_settlement.html'
    
    template = get_template(template_name)
    html_content = template.render(context)

    # Convert HTML to PDF using xhtml2pdf
    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(
        io.StringIO(html_content),
        dest=pdf_buffer
    )

    if pisa_status.err:
        return None

    # Save to model
    pdf_filename = f"{invoice.invoice_number}.pdf"
    invoice.pdf_file.save(pdf_filename, ContentFile(pdf_buffer.getvalue()), save=True)
    return invoice
