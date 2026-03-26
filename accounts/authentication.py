from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError, AuthenticationFailed


class OptionalJWTAuthentication(JWTAuthentication):
    """
    JWT authentication that returns None (anonymous user) instead of raising
    AuthenticationFailed when the token is invalid or expired.

    This allows views with AllowAny permission to serve unauthenticated requests
    even when the client sends a stale/expired token in the Authorization header.
    Views that require IsAuthenticated will still correctly deny access (403).
    """

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except (InvalidToken, TokenError, AuthenticationFailed):
            return None
