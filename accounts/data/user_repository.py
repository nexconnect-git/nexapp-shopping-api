"""UserRepository — all ORM queries for the User model."""

from typing import Any, Dict, Optional
from django.db.models import QuerySet

from django.contrib.auth import get_user_model

User = get_user_model()


class UserRepository:
    """Encapsulates all database access for User records."""

    # ── Single-object lookups ─────────────────────────────────────────────────

    @staticmethod
    def get_by_id(user_id: str) -> Optional[User]:
        """Return a User by primary key, or None if not found."""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    @staticmethod
    def get_by_email(email: str) -> Optional[User]:
        """Return a User by email address, or None if not found."""
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            return None

    @staticmethod
    def get_by_username(username: str) -> Optional[User]:
        """Return a User by username, or None if not found."""
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            return None

    @staticmethod
    def get_by_phone(phone: str, role: Optional[str] = None) -> Optional[User]:
        """Return the most recent user for a phone number, optionally restricted by role."""
        queryset = User.objects.filter(phone=phone)
        if role:
            queryset = queryset.filter(role=role)
        return queryset.order_by('-created_at').first()

    # ── Collection queries ────────────────────────────────────────────────────

    @staticmethod
    def get_all() -> QuerySet:
        """Return all users ordered by creation date (newest first)."""
        return User.objects.all().order_by('-created_at')

    @staticmethod
    def filter(**kwargs) -> QuerySet:
        """Return a filtered queryset using arbitrary keyword arguments."""
        return User.objects.filter(**kwargs)

    @staticmethod
    def get_customers() -> QuerySet:
        """Return all users with role='customer' ordered newest first."""
        return User.objects.filter(role='customer').order_by('-created_at')

    @staticmethod
    def get_staff() -> QuerySet:
        """Return all staff users ordered newest first."""
        return User.objects.filter(is_staff=True).order_by('-created_at')

    @staticmethod
    def get_admin_users() -> QuerySet:
        """Return admin-role users only for the admin access screen."""
        return User.objects.filter(role='admin').order_by('-created_at')

    @staticmethod
    def superuser_exists() -> bool:
        """Return True if at least one superuser account exists."""
        return User.objects.filter(is_superuser=True).exists()

    # ── Mutations ─────────────────────────────────────────────────────────────

    @staticmethod
    def create(**kwargs) -> User:
        """Create and return a new user (password must be hashed by caller)."""
        return User.objects.create(**kwargs)

    @staticmethod
    def update(user: User, data: Dict[str, Any]) -> User:
        """Apply a dictionary of field updates to an existing user and save."""
        for key, value in data.items():
            setattr(user, key, value)
        user.save()
        return user

    @staticmethod
    def delete(user: User) -> None:
        """Delete a user record."""
        user.delete()

    # ── Convenience ───────────────────────────────────────────────────────────

    @staticmethod
    def get_customer_by_id(user_id: str) -> Optional[User]:
        """Return a customer User by PK, or None if not found or wrong role."""
        try:
            return User.objects.get(pk=user_id, role='customer')
        except User.DoesNotExist:
            return None
