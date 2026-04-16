from rest_framework import serializers
from vendors.models.vendor_wallet import VendorWalletTransaction

class VendorWalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorWalletTransaction
        fields = [
            'id', 'vendor', 'amount', 'transaction_type', 
            'source', 'reference_id', 'description', 
            'balance_after', 'created_at'
        ]
        read_only_fields = fields
