"""
Helpers for invoice number generation and tax calculation.
"""
import random
import string
from decimal import Decimal


_TYPE_PREFIX_MAP = {
    'customer_receipt':  'RCPT',
    'vendor_settlement': 'VSTL',
    'delivery_payout':   'DPLY',
}

DEFAULT_TAX_RATE = Decimal('0.10')  # 10%


def generate_invoice_number(invoice_type: str) -> str:
    """Generate a unique invoice number based on invoice type.

    Format: <TYPE_PREFIX>-<8-char alphanumeric suffix>
    e.g. RCPT-A3BF92ZK
    """
    prefix = _TYPE_PREFIX_MAP.get(invoice_type, 'INV')
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f'{prefix}-{suffix}'


def calculate_tax(amount: Decimal, tax_rate: Decimal = DEFAULT_TAX_RATE) -> Decimal:
    """Return the tax amount for a given subtotal and tax rate."""
    return (amount * tax_rate).quantize(Decimal('0.01'))


def calculate_total(amount: Decimal, tax_amount: Decimal) -> Decimal:
    """Return amount + tax_amount."""
    return amount + tax_amount
