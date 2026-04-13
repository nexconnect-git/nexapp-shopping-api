"""Firebase Cloud Messaging (FCM) service."""

import logging

from django.conf import settings

from notifications.data import DeviceTokenRepository

logger = logging.getLogger(__name__)


class FCMService:
    """Handles sending push notifications via Firebase Cloud Messaging.

    In a production deployment this would use ``google-auth`` and POST to
    the FCM v1 HTTP API.  The current implementation is a stub that logs
    the outbound message instead.
    """

    def __init__(self):
        self._server_key = getattr(settings, 'FCM_SERVER_KEY', None)

    def send_push(self, user_id, title: str, body: str, data: dict | None = None) -> bool:
        """Send a push notification to all registered devices for a user.

        Args:
            user_id: The user's UUID/PK whose device tokens to target.
            title: Notification title string.
            body: Notification body text.
            data: Optional extra payload dict attached to the push message.

        Returns:
            True if the push was attempted, False if skipped (no key / no tokens).
        """
        if not self._server_key:
            logger.warning("FCM_SERVER_KEY not set. Skipping push notification.")
            return False

        tokens = DeviceTokenRepository.get_tokens_for_user(user_id)
        if not tokens:
            return False

        # Stub: log instead of making real HTTP call.
        logger.info(
            "Mock FCM Push to %d device(s) for user %s: %s - %s",
            len(tokens),
            user_id,
            title,
            body,
        )
        # Real implementation would do something like:
        #   import requests
        #   for token in tokens:
        #       requests.post(FCM_ENDPOINT, json={...}, headers={...})
        return True
