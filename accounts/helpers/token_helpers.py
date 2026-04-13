"""JWT token and password helpers for the accounts app."""

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


def verify_password(user: User, raw_password: str) -> bool:
    """Check whether ``raw_password`` matches the user's stored hash.

    Args:
        user: The User instance to check against.
        raw_password: The plain-text password to verify.

    Returns:
        True if the password matches, False otherwise.
    """
    return user.check_password(raw_password)
