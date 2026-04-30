"""JWT token and password helpers for the accounts app."""

from django.conf import settings
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models.user import User


def generate_tokens_for_user(user: User) -> dict:
    """Generate a refresh/access token pair for the given user.

    Args:
        user: The authenticated User instance.

    Returns:
        Dictionary with ``refresh`` and ``access`` JWT strings.
    """
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Persist the refresh token in a secure HttpOnly cookie."""
    response.set_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.AUTH_REFRESH_COOKIE_SECURE,
        samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE,
        path='/',
        domain=settings.AUTH_REFRESH_COOKIE_DOMAIN or None,
    )


def clear_refresh_cookie(response: Response) -> None:
    """Remove the refresh cookie from the client."""
    response.delete_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        path='/',
        domain=settings.AUTH_REFRESH_COOKIE_DOMAIN or None,
        samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE,
    )


def verify_password(user: User, raw_password: str) -> bool:
    """Check whether ``raw_password`` matches the user's stored hash.

    Args:
        user: The User instance to check against.
        raw_password: The plain-text password to verify.

    Returns:
        True if the password matches, False otherwise.
    """
    return user.check_password(raw_password)
