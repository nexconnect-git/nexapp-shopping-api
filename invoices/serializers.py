from rest_framework import serializers
from .models import Invoice

class InvoiceSerializer(serializers.ModelSerializer):
    invoice_type_display = serializers.CharField(source='get_invoice_type_display', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True, allow_null=True)
    vendor_name = serializers.CharField(source='vendor.store_name', read_only=True, allow_null=True)
    recipient_email = serializers.EmailField(source='recipient.email', read_only=True, allow_null=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'invoice_type', 'invoice_type_display',
            'order', 'order_number', 'vendor', 'vendor_name', 'recipient', 'recipient_email',
            'pdf_file', 'amount', 'tax_amount', 'notes', 'issued_at'
        ]
        read_only_fields = ['id', 'invoice_number', 'issued_at']
