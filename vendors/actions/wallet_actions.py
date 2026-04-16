from decimal import Decimal
from django.db import transaction

from vendors.models.vendor import Vendor
from vendors.models.vendor_wallet import VendorWalletTransaction

class VendorWalletAction:
    @staticmethod
    @transaction.atomic
    def credit_vendor(vendor_id: str, amount: Decimal, source: str, reference_id: str, description: str = "") -> VendorWalletTransaction:
        """
        Credit the vendor's wallet balance and create a ledger entry.
        """
        vendor = Vendor.objects.select_for_update().get(id=vendor_id)
        
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Credit amount must be greater than zero.")
            
        vendor.wallet_balance += amount
        vendor.save(update_fields=['wallet_balance', 'updated_at'])
        
        txn = VendorWalletTransaction.objects.create(
            vendor=vendor,
            amount=amount,
            transaction_type='credit',
            source=source,
            reference_id=reference_id,
            description=description,
            balance_after=vendor.wallet_balance
        )
        return txn

    @staticmethod
    @transaction.atomic
    def debit_vendor(vendor_id: str, amount: Decimal, source: str, reference_id: str, description: str = "") -> VendorWalletTransaction:
        """
        Debit the vendor's wallet balance and create a ledger entry.
        """
        vendor = Vendor.objects.select_for_update().get(id=vendor_id)
        
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Debit amount must be greater than zero.")
            
        if vendor.wallet_balance < amount:
            raise ValueError(f"Insufficient vendor wallet balance. Available: ₹{vendor.wallet_balance}, Requested: ₹{amount}")
            
        vendor.wallet_balance -= amount
        vendor.save(update_fields=['wallet_balance', 'updated_at'])
        
        txn = VendorWalletTransaction.objects.create(
            vendor=vendor,
            amount=amount,
            transaction_type='debit',
            source=source,
            reference_id=reference_id,
            description=description,
            balance_after=vendor.wallet_balance
        )
        return txn
