"""
TicketNotificationService — creates in-app notifications (and any future
email/push channels) when a support ticket changes state.
"""

from notifications.models import Notification
from support.models import SupportTicket


class TicketNotificationService:
    """Handles all notification side-effects for SupportTicket events."""

    @staticmethod
    def notify_vendor_response(ticket: SupportTicket) -> None:
        """Create an in-app notification telling the vendor their ticket was responded to.

        Args:
            ticket: The SupportTicket that received an admin response.
        """
        Notification.objects.create(
            user=ticket.vendor.user,
            title='Support Ticket Updated',
            message=f'Your ticket "{ticket.subject}" has been responded to.',
            notification_type='system',
            data={'ticket_id': str(ticket.id)},
        )

    @staticmethod
    def notify_vendor_status_change(ticket: SupportTicket, new_status: str) -> None:
        """Notify the vendor when a ticket's status changes.

        Args:
            ticket: The affected SupportTicket.
            new_status: The new human-readable or raw status string.
        """
        Notification.objects.create(
            user=ticket.vendor.user,
            title='Support Ticket Status Changed',
            message=f'Your ticket "{ticket.subject}" status changed to {new_status}.',
            notification_type='system',
            data={'ticket_id': str(ticket.id), 'status': new_status},
        )

    @staticmethod
    def notify_vendor_closed(ticket: SupportTicket) -> None:
        """Notify the vendor that their ticket has been closed.

        Args:
            ticket: The closed SupportTicket.
        """
        Notification.objects.create(
            user=ticket.vendor.user,
            title='Support Ticket Closed',
            message=f'Your ticket "{ticket.subject}" has been closed.',
            notification_type='system',
            data={'ticket_id': str(ticket.id)},
        )
