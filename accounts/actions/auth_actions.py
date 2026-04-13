"""Auth actions — orchestrate registration and login business logic."""

from django.contrib.auth import authenticate

from accounts.data.user_repository import UserRepository
from accounts.helpers.token_helpers import generate_tokens_for_user
from accounts.serializers.user_serializers import (
    UserRegistrationSerializer,
    UserProfileSerializer,
)


class RegisterAction:
    """Orchestrates new-user registration."""

    def __init__(self, data: dict):
        self._data = data

    def execute(self) -> dict:
        """Validate, create the user, and return profile + tokens.

        Returns:
            Dictionary with ``user`` profile data and ``tokens``.

        Raises:
            rest_framework.exceptions.ValidationError: on invalid input.
        """
        serializer = UserRegistrationSerializer(data=self._data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = generate_tokens_for_user(user)
        return {
            'user': UserProfileSerializer(user).data,
            'tokens': tokens,
        }


class LoginAction:
    """Orchestrates credential validation and token issuance."""

    def __init__(self, username: str, password: str):
        self._username = username
        self._password = password

    def execute(self) -> dict:
        """Authenticate the user and return profile + tokens.

        Returns:
            Dictionary with ``user`` profile data and ``tokens``.

        Raises:
            ValueError: If credentials are missing or invalid.
        """
        if not self._username or not self._password:
            raise ValueError('Username and password are required.')

        user = authenticate(username=self._username, password=self._password)
        if user is None:
            raise ValueError('Invalid credentials.')

        tokens = generate_tokens_for_user(user)
        return {
            'user': UserProfileSerializer(user).data,
            'tokens': tokens,
        }
