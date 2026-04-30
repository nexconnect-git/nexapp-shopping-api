"""Custom Channels middleware for JWT-authenticated WebSocket connections."""

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
WS_AUTH_SUBPROTOCOL = 'nexconnect.jwt'


@database_sync_to_async
def get_user_from_token(token):
    try:
        access_token = AccessToken(token)
        user_id = access_token['user_id']
        return User.objects.get(id=user_id)
    except Exception:
        return AnonymousUser()


def get_token_from_subprotocols(scope):
    """Read the JWT from the Sec-WebSocket-Protocol header."""
    headers = dict(scope.get('headers', []))
    raw_value = headers.get(b'sec-websocket-protocol', b'').decode()
    protocols = [item.strip() for item in raw_value.split(',') if item.strip()]

    if len(protocols) >= 2 and protocols[0] == WS_AUTH_SUBPROTOCOL:
        scope['ws_subprotocol'] = WS_AUTH_SUBPROTOCOL
        return protocols[1]
    return None


class JWTAuthMiddleware(BaseMiddleware):
    """Attach the authenticated user to the WebSocket scope."""

    async def __call__(self, scope, receive, send):
        token = get_token_from_subprotocols(scope)
        if token:
            scope['user'] = await get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()

        return await super().__call__(scope, receive, send)
