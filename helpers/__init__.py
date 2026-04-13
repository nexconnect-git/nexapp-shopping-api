"""
Global helper utilities for the NexConnect backend.

This package exposes reusable, app-agnostic functions and classes that are
shared across multiple Django apps, enforcing the DRY principle at the
project level.

Sub-modules
-----------
geo_helpers     – Great-circle distance and geographic utilities.
request_helpers – HTTP request utilities (client IP extraction, etc.).
view_helpers    – Base classes and mixins shared by DRF views.
"""

from helpers.geo_helpers import haversine
from helpers.request_helpers import get_client_ip
from helpers.view_helpers import BaseDetailView
from helpers.encryption import encrypt_value, decrypt_value, mask_account_number
from helpers.validators import validate_pan, validate_gstin, validate_ifsc

__all__ = [
    "haversine",
    "get_client_ip",
    "BaseDetailView",
    "encrypt_value",
    "decrypt_value",
    "mask_account_number",
    "validate_pan",
    "validate_gstin",
    "validate_ifsc",
]
