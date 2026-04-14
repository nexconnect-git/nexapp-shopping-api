"""Firebase Cloud Messaging (FCM) service using the firebase-admin SDK."""

import logging

import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings

from notifications.data import DeviceTokenRepository

logger = logging.getLogger(__name__)

_firebase_app = None


def _get_firebase_app():
    """Return the initialized Firebase app, initializing it lazily on first call."""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    service_account_path = getattr(settings, 'FIREBASE_SERVICE_ACCOUNT_PATH', None)
    if not service_account_path:
        logger.warning("FIREBASE_SERVICE_ACCOUNT_PATH not set — FCM disabled.")
        return None

    try:
        # Avoid re-initializing if already done (e.g. in tests)
        _firebase_app = firebase_admin.get_app()
    except ValueError:
        try:
            cred = credentials.Certificate(service_account_path)
            _firebase_app = firebase_admin.initialize_app(cred)
        except Exception as exc:
            logger.error("Failed to initialize Firebase app: %s", exc)
            return None

    return _firebase_app


class FCMService:
    """Sends push notifications via Firebase Cloud Messaging (FCM v1 HTTP API).

    Requires ``FIREBASE_SERVICE_ACCOUNT_PATH`` in settings pointing to the
    downloaded Firebase service account JSON file.
    """

    def send_push(self, user_id, title: str, body: str, data: dict | None = None) -> bool:
        """Send a push notification to all registered devices for a user.

        Args:
            user_id: The user's UUID/PK whose device tokens to target.
            title: Notification title string.
            body: Notification body text.
            data: Optional extra payload dict (all values must be strings).

        Returns:
            True if at least one message was sent successfully, False otherwise.
        """
        app = _get_firebase_app()
        if app is None:
            return False

        tokens = DeviceTokenRepository.get_tokens_for_user(user_id)
        if not tokens:
            logger.debug("No device tokens for user %s — skipping push.", user_id)
            return False

        # FCM data payload values must all be strings
        str_data = {k: str(v) for k, v in (data or {}).items()}

        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=str_data,
            tokens=list(tokens),
        )

        try:
            response = messaging.send_multicast(message)
        except Exception as exc:
            logger.error("FCM send_multicast error for user %s: %s", user_id, exc)
            return False

        logger.info(
            "FCM push for user %s — success: %d, failure: %d",
            user_id,
            response.success_count,
            response.failure_count,
        )

        # Remove stale tokens that FCM has invalidated
        if response.failure_count:
            self._purge_invalid_tokens(tokens, response.responses)

        return response.success_count > 0

    @staticmethod
    def _purge_invalid_tokens(tokens: list, responses: list) -> None:
        """Delete device tokens that FCM reports as invalid/unregistered."""
        from notifications.models import DeviceToken

        for token, resp in zip(tokens, responses):
            if not resp.success and resp.exception:
                error_code = getattr(resp.exception, 'code', '')
                if error_code in (
                    'registration-token-not-registered',
                    'invalid-registration-token',
                ):
                    deleted, _ = DeviceToken.objects.filter(token=token).delete()
                    if deleted:
                        logger.info("Purged stale FCM token: %s", token[:20])
