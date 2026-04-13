"""
Backward-compatibility shim.

All view mixins have been moved to ``helpers.view_helpers``.
Import directly from there in new code.
"""

from helpers.view_helpers import BaseDetailView

__all__ = ["BaseDetailView"]
