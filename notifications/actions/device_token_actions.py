from rest_framework.exceptions import ValidationError

from notifications.data import DeviceTokenRepository


class RegisterDeviceTokenAction:
    def __init__(self, repository: DeviceTokenRepository = None):
        self.repository = repository or DeviceTokenRepository()

    def execute(self, user, token: str, platform: str = 'web') -> bool:
        if not token:
            raise ValidationError({'error': 'token is required'})
        _, created = self.repository.update_or_create(
            token=token,
            defaults={'user': user, 'platform': platform},
        )
        return created
