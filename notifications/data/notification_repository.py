"""Repository for all Notification ORM operations."""

from django.db.models import Q, QuerySet

from notifications.models import Notification


class NotificationRepository:
    """Encapsulates all ORM queries for the Notification model."""

    @staticmethod
    def get_by_id(pk) -> Notification | None:
        """Return a Notification by primary key, or None if not found."""
        try:
            return Notification.objects.get(pk=pk)
        except Notification.DoesNotExist:
            return None

    @staticmethod
    def get_by_id_and_user(pk, user) -> Notification | None:
        """Return a Notification owned by the given user, or None."""
        try:
            return Notification.objects.get(pk=pk, user=user)
        except Notification.DoesNotExist:
            return None

    @staticmethod
    def get_all() -> QuerySet:
        """Return all notifications ordered by newest first."""
        return Notification.objects.select_related('user').order_by('-created_at')

    @staticmethod
    def filter_for_user(user) -> QuerySet:
        """Return all notifications belonging to the given user."""
        return Notification.objects.filter(user=user)

    @staticmethod
    def filter_admin(search=None, notification_type=None, is_read=None) -> QuerySet:
        """Return a filtered queryset for admin list views.

        Args:
            search: Optional text to match against title, message, or username.
            notification_type: Optional type string to filter on.
            is_read: Optional bool to filter read/unread.

        Returns:
            Filtered QuerySet of Notification instances.
        """
        qs = Notification.objects.select_related('user').order_by('-created_at')

        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(message__icontains=search)
                | Q(user__username__icontains=search)
            )
        if notification_type:
            qs = qs.filter(notification_type=notification_type)
        if is_read is not None:
            qs = qs.filter(is_read=is_read)

        return qs

    @staticmethod
    def count_unread_for_user(user) -> int:
        """Return the number of unread notifications for the given user."""
        return Notification.objects.filter(user=user, is_read=False).count()

    @staticmethod
    def create(**kwargs) -> Notification:
        """Create and return a new Notification."""
        return Notification.objects.create(**kwargs)

    @staticmethod
    def bulk_create(notifications: list) -> list:
        """Bulk-insert a list of unsaved Notification instances."""
        return Notification.objects.bulk_create(notifications)

    @staticmethod
    def bulk_create_ignore_conflicts(notifications: list) -> list:
        """Bulk-insert ignoring duplicate conflicts."""
        return Notification.objects.bulk_create(notifications, ignore_conflicts=True)

    @staticmethod
    def mark_read(notification: Notification) -> Notification:
        """Set is_read=True on a single notification and save."""
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return notification

    @staticmethod
    def mark_all_read_for_user(user) -> int:
        """Bulk-update all unread notifications for the user. Returns update count."""
        return Notification.objects.filter(user=user, is_read=False).update(is_read=True)

    @staticmethod
    def delete(notification: Notification) -> None:
        """Delete a single notification."""
        notification.delete()

    @staticmethod
    def get_or_create(**kwargs):
        """Thin wrapper around ORM get_or_create."""
        return Notification.objects.get_or_create(**kwargs)
