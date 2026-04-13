"""Repository for all DeviceToken ORM operations."""

from notifications.models import DeviceToken


class DeviceTokenRepository:
    """Encapsulates all ORM queries for the DeviceToken model."""

    @staticmethod
    def get_by_id(pk) -> DeviceToken | None:
        """Return a DeviceToken by primary key, or None if not found."""
        try:
            return DeviceToken.objects.get(pk=pk)
        except DeviceToken.DoesNotExist:
            return None

    @staticmethod
    def get_all():
        """Return all device tokens."""
        return DeviceToken.objects.all()

    @staticmethod
    def filter_by_user(user):
        """Return all device tokens for a specific user."""
        return DeviceToken.objects.filter(user=user)

    @staticmethod
    def get_tokens_for_user(user_id) -> list:
        """Return a flat list of token strings for the given user ID."""
        return list(DeviceToken.objects.filter(user_id=user_id).values_list('token', flat=True))

    @staticmethod
    def create(**kwargs) -> DeviceToken:
        """Create and return a new DeviceToken."""
        return DeviceToken.objects.create(**kwargs)

    @staticmethod
    def update_or_create(token: str, defaults: dict):
        """Upsert a DeviceToken by token string.

        Args:
            token: The unique FCM/push token string.
            defaults: Field values to set on create or update.

        Returns:
            Tuple of (DeviceToken instance, created bool).
        """
        return DeviceToken.objects.update_or_create(token=token, defaults=defaults)

    @staticmethod
    def delete(device_token: DeviceToken) -> None:
        """Delete a single device token."""
        device_token.delete()

    @staticmethod
    def filter(conditions: dict):
        """Generic filter pass-through."""
        return DeviceToken.objects.filter(**conditions)
