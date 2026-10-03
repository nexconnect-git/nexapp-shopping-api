from rest_framework import serializers
from helpers.media_helpers import safe_media_url


class SafeFileField(serializers.FileField):
    def to_representation(self, value):
        return safe_media_url(value, request=self.context.get('request'))


class SafeImageField(serializers.ImageField):
    def to_representation(self, value):
        return safe_media_url(value, request=self.context.get('request'))


class StrictIntegerField(serializers.IntegerField):
    def to_internal_value(self, data):
        if isinstance(data, bool) or (isinstance(data, float) and not data.is_integer()):
            self.fail('invalid')
        return super().to_internal_value(data)
