import re

def validate_pan(pan: str) -> bool:
    """Validate Indian PAN number format: AAAAA9999A"""
    return bool(re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', pan.upper()))

def validate_gstin(gstin: str) -> bool:
    """Validate Indian GSTIN format: 22AAAAA0000A1Z5"""
    return bool(re.match(
        r'^[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$',
        gstin.upper()
    ))

def validate_ifsc(ifsc: str) -> bool:
    """Validate IFSC code format: AAAA0NNNNNN"""
    return bool(re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc.upper()))
