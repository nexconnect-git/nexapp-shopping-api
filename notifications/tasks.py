import logging
from django_rq import job
from django.core.mail import EmailMessage
from django.conf import settings
from invoices.utils import generate_pdf_invoice
from invoices.models import Invoice

logger = logging.getLogger(__name__)

@job('default')
def send_async_email(subject, body, to_emails, attachment_path=None, attachment_filename=None):
    """
    Background job to send an email. Optionally accepts a PDF attachment file path.
    """
    try:
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to_emails
        )
        if attachment_path and attachment_filename:
            with open(attachment_path, 'rb') as f:
                email.attach(attachment_filename, f.read(), 'application/pdf')
        
        email.send(fail_silently=False)
        logger.info(f"Successfully sent email to {to_emails}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_emails}: {str(e)}")


@job('default')
def process_order_invoice_and_email(order_id):
    """
    Background job to generate a customer invoice PDF and email it after an order completes.
    """
    from orders.models import Order
    try:
        order = Order.objects.get(id=order_id)
        
        # 1. Create the Invoice record
        invoice, created = Invoice.objects.get_or_create(
            order=order,
            invoice_type='customer_receipt',
            defaults={
                'recipient': order.customer,
                'vendor': order.vendor,
                'amount': order.total,
                'tax_amount': 0, # Depending on business logic
            }
        )
        
        # 2. Generate PDF
        if not invoice.pdf_file:
            invoice = generate_pdf_invoice(invoice.id)
            if not invoice:
                logger.error(f"PDF generation failed for order {order_id}")
                return

        # 3. Queue the email job
        attachment_path = invoice.pdf_file.path if invoice.pdf_file else None
        attachment_name = f"Invoice_{invoice.invoice_number}.pdf"
        
        body_text = f"Hello {order.customer.first_name},\n\nThank you for your order {order.order_number}! Your invoice is attached.\n\nBest,\nNexConnect Team"
        
        # We can directly call the email sending here since we are already in a background worker, 
        # or we could enqueue it again. Direct call is simpler.
        if attachment_path:
            email = EmailMessage(
                subject=f"Your NexConnect Order Invoice #{order.order_number}",
                body=body_text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[order.customer.email]
            )
            with open(attachment_path, 'rb') as f:
                email.attach(attachment_name, f.read(), 'application/pdf')
            
            email.send(fail_silently=False)
            logger.info(f"Successfully sent invoice email for order {order.order_number}")

    except Exception as e:
        logger.error(f"Error processing invoice for order {order_id}: {str(e)}")
