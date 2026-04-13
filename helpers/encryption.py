"""
Encryption utilities for sensitive data (bank account numbers, etc.)
Uses Fernet symmetric encryption derived from Django's SECRET_KEY.
"""
import base64
import hashlib
from cryptography.fernet import Fernet

def _get_fernet() -> Fernet:
    from django.conf import settings
    raw_key = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
    fernet_key = base64.urlsafe_b64encode(raw_key)
    return Fernet(fernet_key)

def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value. Returns base64-encoded ciphertext string."""
    if not plaintext:
        return ''
    return _get_fernet().encrypt(plaintext.encode('utf-8')).decode('utf-8')

def decrypt_value(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted string. Returns empty string on failure."""
    if not ciphertext:
        return ''
    try:
        return _get_fernet().decrypt(ciphertext.encode('utf-8')).decode('utf-8')
    except Exception:
        return ''

def mask_account_number(account_number: str) -> str:
    """Return masked account number showing only last 4 digits."""
    if not account_number:
        return ''
    if len(account_number) <= 4:
        return '*' * len(account_number)
    return 'X' * (len(account_number) - 4) + account_number[-4:]
