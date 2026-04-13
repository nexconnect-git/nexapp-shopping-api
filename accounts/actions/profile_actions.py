"""Profile actions — orchestrate profile updates and password changes."""

from django.db import transaction

from accounts.data.user_repository import UserRepository
from accounts.models.user import User


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
    def execute(self) -> None:
        """Verify and change the user's password.

        Raises:
            ValueError: If ``current_password`` does not match the stored hash.
        """
        if not self._user.check_password(self._current_password):
            raise ValueError('Current password is incorrect.')

        self._user.set_password(self._new_password)
        self._user.force_password_change = False
        self._user.temp_password = ''
        self._user.save(
            update_fields=['password', 'force_password_change', 'temp_password']
        )
