"""Service layer for the accounts app.

Encapsulates business logic that should not live directly in views,
keeping views thin and the logic independently testable.
"""

from typing import Dict, Any

from django.db import transaction
from django.db.models import Sum

from accounts.models import User
from orders.models import Order
from vendors.models import Vendor
from products.models import Product
from delivery.models import DeliveryPartner


class AccountService:
    """Stateless service class for account-related business operations."""

    @staticmethod
    def get_admin_stats() -> Dict[str, Any]:
        """Compute platform-wide aggregate statistics for the admin dashboard.

        Queries counts and totals across users, vendors, products, orders,
        and delivery partners.

        Returns:
            A dictionary of platform statistics keyed by metric name.
        """
        revenue = (
            Order.objects.filter(status="delivered").aggregate(total=Sum("total"))[
                "total"
            ]
            or 0
        )
        return {
            "customers": User.objects.filter(role="customer").count(),
            "vendors": Vendor.objects.count(),
            "pending_vendors": Vendor.objects.filter(status="pending").count(),
            "delivery_partners": DeliveryPartner.objects.count(),
            "pending_delivery_partners": DeliveryPartner.objects.filter(
                is_approved=False
            ).count(),
            "products": Product.objects.count(),
            "orders": Order.objects.count(),
            "orders_placed": Order.objects.filter(status="placed").count(),
            "orders_delivering": Order.objects.filter(
                status__in=["picked_up", "on_the_way"]
            ).count(),
            "orders_delivered": Order.objects.filter(status="delivered").count(),
            "total_revenue": revenue,
        }

    @staticmethod
    @transaction.atomic
    def change_user_password(
        user: User, current_password: str, new_password: str
    ) -> None:
        """Change a user's password after verifying the current one.

        Args:
            user: The user whose password should be changed.
            current_password: The user's existing password for verification.
            new_password: The new password to set.

        Raises:
            ValueError: If ``current_password`` does not match the stored hash.
        """
        if not user.check_password(current_password):
            raise ValueError("Current password is incorrect.")

        user.set_password(new_password)
        user.force_password_change = False
        user.temp_password = ""
        user.save(update_fields=["password", "force_password_change", "temp_password"])

    @staticmethod
    @transaction.atomic
    def update_admin_customer(user_id: str, data: dict) -> User:
        """Update mutable fields on a customer account (admin use only).

        Args:
            user_id: UUID primary key of the target customer.
            data: Dictionary of field names to new values.

        Returns:
            The updated ``User`` instance.

        Raises:
            ValueError: If no customer with the given ``user_id`` exists.
        """
        try:
            user = User.objects.get(pk=user_id, role="customer")
        except User.DoesNotExist:
            raise ValueError("Customer not found.")

        for key, value in data.items():
            setattr(user, key, value)
        user.save()
        return user
