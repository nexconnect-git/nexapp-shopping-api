from rest_framework.permissions import BasePermission

from accounts.admin_access import allows, required_permission


class IsAdminRole(BasePermission):
    """Allows access only to users with role='admin'."""

    def has_permission(self, request, view):
        authenticated = bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == 'admin'
        )
        if not authenticated:
            return False
        permission = required_permission(view, request.method)
        return permission is None or allows(request.user, permission)


class IsSuperUser(BasePermission):
    """Allows access only to superusers."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
            and request.user.is_active
            and request.user.role == 'admin'
        )


class HasAdminPermission(BasePermission):
    """Allows superusers or admins with the view's required admin permission."""

    message = 'You do not have permission to perform this admin action.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.role == 'admin'):
            return False
        if user.is_superuser:
            return True

        required_permission = getattr(view, 'required_admin_permission', None)
        if not required_permission:
            return True

        permission = required_permission.replace('.manage', '.view') if request.method in ('GET', 'HEAD', 'OPTIONS') else required_permission
        return allows(user, permission)


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
        if request.user.force_password_change:
            self.message = 'Change your password before using vendor operations.'
            return False
        return request.user.role == 'vendor' and request.user.vendor_profile.status == 'approved'


class IsDeliveryPartner(BasePermission):
    """Allows access only to users who have an associated delivery profile."""
    message = 'You must have a delivery partner profile to access this resource.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return hasattr(request.user, 'delivery_profile') and (
            request.user.delivery_profile is not None
        )
