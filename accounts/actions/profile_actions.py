"""Profile actions — orchestrate profile updates and password changes."""

from django.db import transaction
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError

from accounts.data.user_repository import UserRepository
from accounts.models.user import User
from accounts.data.password_reset_repository import PasswordResetRepository


class UpdateProfileAction:
    """Partially update a user's profile fields."""

    def __init__(self, user: User, data: dict):
        self._user = user
        self._data = data

    def execute(self) -> User:
        """Apply validated field updates to the user and persist.

        Returns:
            The updated User instance.
        """
        return UserRepository.update(self._user, self._data)


class ChangePasswordAction:
    """Verify the current password then set a new one."""

    def __init__(self, user: User, current_password: str, new_password: str):
        self._user = user
        self._current_password = current_password
        self._new_password = new_password

    @transaction.atomic
    def execute(self) -> User:
        """Verify and change the user's password.

        Raises:
            ValueError: If ``current_password`` does not match the stored hash.
        """
        self._user = PasswordResetRepository.locked_user(self._user.pk)
        if not self._user.check_password(self._current_password):
            raise ValueError('Current password is incorrect.')
        try:
            validate_password(self._new_password, self._user)
        except DjangoValidationError as exc:
            raise ValidationError({'new_password': exc.messages}) from exc

        self._user.set_password(self._new_password)
        self._user.force_password_change = False
        self._user.temp_password = ''
        self._user.save(
            update_fields=['password', 'force_password_change', 'temp_password']
        )
        PasswordResetRepository.invalidate_sessions(self._user)
        return self._user
