from rest_framework import serializers

from helpers.media_helpers import safe_media_url


class SafeFileField(serializers.FileField):
    def to_representation(self, value):
        return safe_media_url(value, request=self.context.get("request"))


class SafeImageField(serializers.ImageField):
    def to_representation(self, value):
        return safe_media_url(value, request=self.context.get("request"))
