from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Allows access only to users with role='admin'."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == 'admin'
        )


class IsSuperUser(BasePermission):
    """Allows access only to superusers."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
        )


class IsVendor(BasePermission):
    """Allows access only to users who have an associated vendor profile."""
    message = 'You must have a vendor profile to access this resource.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return hasattr(request.user, 'vendor_profile') and (
            request.user.vendor_profile is not None
        )


class IsApprovedVendor(BasePermission):
    """Allows access only to vendors whose account has been approved by admin."""
    message = 'Your vendor account is pending approval. You will be notified once approved.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if not hasattr(request.user, 'vendor_profile') or request.user.vendor_profile is None:
            return False
        return request.user.vendor_profile.status == 'approved'


class IsDeliveryPartner(BasePermission):
    """Allows access only to users who have an associated delivery profile."""
    message = 'You must have a delivery partner profile to access this resource.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return hasattr(request.user, 'delivery_profile') and (
            request.user.delivery_profile is not None
        )
