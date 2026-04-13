"""
Repository layer for SupportTicket — all ORM queries live here.
"""

from typing import Optional
from support.models import SupportTicket


class SupportTicketRepository:
    """All database access for SupportTicket objects."""

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    @staticmethod
    def get_by_id(ticket_id) -> Optional[SupportTicket]:
        """Return a single SupportTicket by primary key, or None."""
        try:
            return SupportTicket.objects.get(pk=ticket_id)
        except SupportTicket.DoesNotExist:
            return None

    @staticmethod
    def get_by_id_and_vendor(ticket_id, vendor) -> Optional[SupportTicket]:
        """Return a ticket owned by *vendor*, or None."""
        try:
            return SupportTicket.objects.get(pk=ticket_id, vendor=vendor)
        except SupportTicket.DoesNotExist:
            return None

    @staticmethod
    def get_all():
        """Return all tickets ordered by newest first with vendor pre-fetched."""
        return SupportTicket.objects.select_related('vendor').order_by('-created_at')

    @staticmethod
    def get_for_vendor(vendor):
        """Return all tickets belonging to *vendor*."""
        return SupportTicket.objects.filter(vendor=vendor)

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    @staticmethod
    def filter(**kwargs):
        """Generic filter delegating kwargs directly to the ORM."""
        return SupportTicket.objects.filter(**kwargs)

    @staticmethod
    def filter_all_by_status(status_value):
        """Return all tickets with the given *status_value*."""
        return (
            SupportTicket.objects
            .select_related('vendor')
            .filter(status=status_value)
            .order_by('-created_at')
        )

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    @staticmethod
    def create(vendor, **fields) -> SupportTicket:
        """Create and return a new SupportTicket for *vendor*."""
        return SupportTicket.objects.create(vendor=vendor, **fields)

    @staticmethod
    def update(ticket: SupportTicket, **fields) -> SupportTicket:
        """Apply *fields* to *ticket*, save, and return the updated instance."""
        for attr, value in fields.items():
            setattr(ticket, attr, value)
        ticket.save()
        return ticket

    @staticmethod
    def delete(ticket: SupportTicket) -> None:
        """Hard-delete *ticket* from the database."""
        ticket.delete()
