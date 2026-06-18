from rest_framework.permissions import BasePermission


class IsApprovedDeliveryPartner(BasePermission):
    message = "Delivery partner approval is required."

    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, "is_authenticated", False):
            return False
        partner = getattr(user, "delivery_profile", None)
        return bool(partner and partner.is_approved)
