"""Thin public helper for sending FCM push notifications.

Delegates to ``FCMService`` which uses the firebase-admin SDK.
"""

from notifications.services.fcm_service import FCMService

_service = FCMService()


def send_push(user_id, title: str, body: str, data: dict | None = None) -> bool:
    """Send a push notification to all registered devices for a user.

    Args:
        user_id: The user's UUID/PK whose device tokens to target.
        title: Notification title string.
        body: Notification body text.
        data: Optional extra payload dict (values will be coerced to strings).

    Returns:
        True if at least one message was sent, False if skipped or all failed.
    """
    return _service.send_push(user_id, title=title, body=body, data=data)
