import io
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
from .utils import generate_pdf_invoice


class InvoiceGenerateView(APIView):
    """POST /api/invoices/generate/
    Admins can generate any invoice.
    Vendors can generate invoices for orders belonging to their store.
    Customers can generate receipts for their own orders.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from orders.models import Order as OrderModel

        user = request.user
        data = request.data.copy()

        # Resolve the order and enforce ownership for non-admins
        if getattr(user, 'role', '') != 'admin' and not user.is_superuser:
            invoice_type = data.get('invoice_type')
            
            # Allow vendor settlement statements without an order
            if invoice_type == 'vendor_settlement' and hasattr(user, 'vendor_profile'):
                data.setdefault('vendor', str(user.vendor_profile.id))
            
            else:
                # Default behavior: require order and validate ownership
                order_id = data.get('order')
                if not order_id:
                    return Response({'error': 'order is required.'}, status=status.HTTP_400_BAD_REQUEST)
                try:
                    order = OrderModel.objects.select_related('vendor', 'customer').get(pk=order_id)
                except OrderModel.DoesNotExist:
                    return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

                if hasattr(user, 'vendor_profile') and order.vendor == user.vendor_profile:
                    data.setdefault('vendor', str(user.vendor_profile.id))
                elif order.customer == user:
                    pass
                else:
                    return Response(
                        {'error': 'You do not have permission to generate an invoice for this order.'},
                        status=status.HTTP_403_FORBIDDEN,
                    )

        serializer = InvoiceSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()

        updated_invoice = generate_pdf_invoice(invoice.id)
        if not updated_invoice:
            return Response({'error': 'Failed to generate PDF'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(InvoiceSerializer(updated_invoice).data, status=status.HTTP_201_CREATED)


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
