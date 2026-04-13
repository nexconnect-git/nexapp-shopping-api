"""
Vendor-facing ticket action classes.

Each action class encapsulates one business operation; views call actions,
not the ORM directly.
"""

from django.utils import timezone

from support.data import SupportTicketRepository
from support.helpers import validate_category, validate_priority, validate_status
from support.models import SupportTicket
from support.services import TicketNotificationService


class CreateTicketAction:
    """Create a new support ticket on behalf of a vendor."""

    def __init__(self, repository: SupportTicketRepository = None):
        self.repo = repository or SupportTicketRepository()

    def execute(self, vendor, validated_data: dict) -> SupportTicket:
        """Persist and return a new SupportTicket.

        Args:
            vendor: The Vendor instance submitting the ticket.
            validated_data: Cleaned data dict (from serializer.validated_data).

        Returns:
            The newly created SupportTicket.
        """
        return SupportTicketRepository.create(vendor=vendor, **validated_data)


class RespondToTicketAction:
    """Allow a vendor to add a follow-up message to their own ticket.

    (Distinct from admin responses; reserved for future vendor-reply flows.)
    """

    def execute(self, ticket: SupportTicket, message: str) -> SupportTicket:
        """Append *message* as an updated ticket message and mark in-progress.

        Args:
            ticket: The SupportTicket to update.
            message: The vendor's follow-up message text.

        Returns:
            The updated SupportTicket.
        """
        return SupportTicketRepository.update(
            ticket,
            message=message,
            status='in_progress',
            updated_at=timezone.now(),
        )


class CloseTicketAction:
    """Close a support ticket (vendor-initiated)."""

    def execute(self, ticket: SupportTicket) -> SupportTicket:
        """Set ticket status to 'closed'.

        Args:
            ticket: The SupportTicket to close.

        Returns:
            The updated SupportTicket.
        """
        updated = SupportTicketRepository.update(ticket, status='closed')
        TicketNotificationService.notify_vendor_closed(updated)
        return updated
