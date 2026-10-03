"""JWT token and password helpers for the accounts app."""

from django.conf import settings
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
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
    refresh['portal_role'] = user.role
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


PORTAL_ROLES = ('customer', 'vendor', 'delivery', 'admin')


def requested_portal(request):
    portal = request.data.get('portal')
    if portal is not None and portal not in PORTAL_ROLES:
        raise ValidationError({'portal': 'Invalid portal.'})
    return portal


def refresh_cookie_name(portal=None):
    base = settings.AUTH_REFRESH_COOKIE_NAME
    return f'{base}_{portal}' if portal else base


def refresh_token_from_request(request, portal=None):
    if request.data.get('refresh'):
        return request.data['refresh']
    if portal:
        return request.COOKIES.get(refresh_cookie_name(portal)) or request.COOKIES.get(refresh_cookie_name())
    cookies = [request.COOKIES[refresh_cookie_name(role)] for role in PORTAL_ROLES if refresh_cookie_name(role) in request.COOKIES]
    if len(cookies) == 1:
        return cookies[0]
    if len(cookies) > 1:
        raise ValidationError({'portal': 'Specify the portal to refresh.'})
    return request.COOKIES.get(refresh_cookie_name())


def set_refresh_cookie(response: Response, refresh_token: str, portal: str) -> None:
    """Persist the refresh token in a secure HttpOnly cookie."""
    response.set_cookie(
        key=refresh_cookie_name(portal),
        value=refresh_token,
        httponly=True,
        secure=settings.AUTH_REFRESH_COOKIE_SECURE,
        samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE,
        path='/',
        domain=settings.AUTH_REFRESH_COOKIE_DOMAIN or None,
        max_age=int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()),
    )


def clear_refresh_cookie(response: Response, portal=None) -> None:
    """Remove the refresh cookie from the client."""
    response.delete_cookie(
        key=refresh_cookie_name(portal),
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
