import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from django.http import HttpResponse

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdminRole
from .models import Invoice
from .serializers import InvoiceSerializer


def _generate_pdf_bytes(invoice: Invoice) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "NexConnect Platform")
    
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 70, f"Invoice #: {invoice.invoice_number}")
    c.drawString(50, height - 85, f"Type: {invoice.get_invoice_type_display()}")
    c.drawString(50, height - 100, f"Date: {invoice.issued_at.strftime('%Y-%m-%d %H:%M')}")
    
    # Billing info
    c.drawString(50, height - 130, "Bill To:")
    if invoice.recipient:
        c.drawString(50, height - 145, f"{invoice.recipient.get_full_name()} ({invoice.recipient.email})")
    elif invoice.vendor:
        c.drawString(50, height - 145, f"{invoice.vendor.store_name}")
    
    # Details
    y = height - 190
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Description")
    c.drawString(400, y, "Amount")
    
    y -= 25
    c.setFont("Helvetica", 12)
    desc = f"{invoice.get_invoice_type_display()}"
    if invoice.order:
        desc += f" for Order {invoice.order.order_number}"
    
    lines = simpleSplit(desc, "Helvetica", 12, 330)
    for line in lines:
        c.drawString(50, y, line)
        y -= 15
        
    c.drawString(400, y + len(lines)*15, f"${invoice.amount:.2f}")
    
    y -= 30
    c.drawString(300, y, "Tax:")
    c.drawString(400, y, f"${invoice.tax_amount:.2f}")
    
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(300, y, "Total:")
    c.drawString(400, y, f"${(invoice.amount + invoice.tax_amount):.2f}")
    
    if invoice.notes:
        y -= 50
        c.setFont("Helvetica", 10)
        c.drawString(50, y, "Notes:")
        notes_lines = simpleSplit(invoice.notes, "Helvetica", 10, 500)
        for line in notes_lines:
            y -= 15
            c.drawString(50, y, line)

    c.save()
    return buf.getvalue()


class InvoiceGenerateView(APIView):
    """POST /api/invoices/generate/  (Admin mostly, but could be internal)"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        serializer = InvoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()
        
        pdf_bytes = _generate_pdf_bytes(invoice)
        filename = f"{invoice.invoice_number}.pdf"
        invoice.pdf_file.save(filename, ContentFile(pdf_bytes))
        
        return Response(InvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)


class InvoiceDownloadView(APIView):
    """GET /api/invoices/<pk>/download/  — download the PDF if authorized"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        
        # Access control
        user = request.user
        can_access = False
        if getattr(user, 'role', '') == 'admin' or user.is_superuser:
            can_access = True
        elif invoice.recipient == user:
            can_access = True
        elif invoice.vendor and hasattr(user, 'vendor_profile') and invoice.vendor == user.vendor_profile:
            can_access = True
            
        if not can_access:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
            
        if not invoice.pdf_file:
            return Response({'error': 'PDF not generated yet.'}, status=status.HTTP_404_NOT_FOUND)
            
        response = HttpResponse(invoice.pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{invoice.pdf_file.name.split("/")[-1]}"'
        return response


class UserInvoiceListView(generics.ListAPIView):
    """GET /api/invoices/ — list invoices where user is recipient or vendor"""
    permission_classes = [IsAuthenticated]
    serializer_class = InvoiceSerializer
    
    def get_queryset(self):
        user = self.request.user
        from django.db.models import Q
        qs = Invoice.objects.filter(recipient=user)
        if hasattr(user, 'vendor_profile'):
            qs = qs | Invoice.objects.filter(vendor=user.vendor_profile)
        return qs.order_by('-issued_at')
