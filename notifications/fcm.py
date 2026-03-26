import logging
from django.conf import settings
from .models import DeviceToken

logger = logging.getLogger(__name__)

def send_push(user_id, title, body, data=None):
    """
    Stub for Firebase Cloud Messaging (FCM). 
    In a real app, this would use google-auth and POST to the FCM v1 API.
    """
    server_key = settings.FCM_SERVER_KEY
    if not server_key:
        logger.warning("FCM_SERVER_KEY not set. Skipping push notification.")
        return

    tokens = DeviceToken.objects.filter(user_id=user_id).values_list('token', flat=True)
    if not tokens:
        return

    # Mock implementation of FCM push
    logger.info(f"Mock FCM Push to {len(tokens)} devices for user {user_id}: {title} - {body}")
    # import requests ...
