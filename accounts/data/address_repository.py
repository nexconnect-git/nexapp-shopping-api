"""AddressRepository — all ORM queries for the Address model."""

from typing import Any, Dict, Optional
from django.db.models import QuerySet

from accounts.models.address import Address
from accounts.models.user import User


class AddressRepository:
    """Encapsulates all database access for Address records."""

    # ── Single-object lookups ─────────────────────────────────────────────────

    @staticmethod
    def get_by_id(address_id: str) -> Optional[Address]:
        """Return an Address by primary key, or None if not found."""
        try:
            return Address.objects.get(pk=address_id)
        except Address.DoesNotExist:
            return None

    @staticmethod
    def get_by_id_and_user(address_id: str, user: User) -> Optional[Address]:
        """Return an Address owned by ``user`` by PK, or None if not found."""
        try:
            return Address.objects.get(pk=address_id, user=user)
        except Address.DoesNotExist:
            return None

    # ── Collection queries ────────────────────────────────────────────────────

    @staticmethod
    def get_all() -> QuerySet:
        """Return all addresses."""
        return Address.objects.all()

    @staticmethod
    def filter(**kwargs) -> QuerySet:
        """Return a filtered queryset using arbitrary keyword arguments."""
        return Address.objects.filter(**kwargs)

    @staticmethod
    def get_for_user(user: User) -> QuerySet:
        """Return all addresses belonging to the given user."""
        return Address.objects.filter(user=user)

    # ── Mutations ─────────────────────────────────────────────────────────────

    @staticmethod
    def create(user: User, **kwargs) -> Address:
        """Create and return a new address for the given user."""
        return Address.objects.create(user=user, **kwargs)

    @staticmethod
    def update(address: Address, data: Dict[str, Any]) -> Address:
        """Apply a dictionary of field updates to an existing address and save."""
        for key, value in data.items():
            setattr(address, key, value)
        address.save()
        return address

    @staticmethod
    def delete(address: Address) -> None:
        """Delete an address record."""
        address.delete()
