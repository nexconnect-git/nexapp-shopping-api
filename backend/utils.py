"""
Backward-compatibility shim.

All utility functions have been moved to the top-level ``helpers`` package.
Import directly from ``helpers`` in new code.
"""

from helpers.geo_helpers import haversine
from helpers.request_helpers import get_client_ip

__all__ = ["haversine", "get_client_ip"]
