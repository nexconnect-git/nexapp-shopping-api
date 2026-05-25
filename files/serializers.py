from rest_framework import serializers

from files.models import UploadedFile
from helpers.media_helpers import safe_media_url


class UploadedFileSerializer(serializers.ModelSerializer):
    file_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = UploadedFile
        fields = [
            'id',
            'client_upload_id',
            'original_filename',
            'use_of_image',
            'file_name',
            'file_url',
            'content_type',
            'size',
            'created_at',
        ]
        read_only_fields = fields

    def get_file_name(self, obj):
        return obj.file.name

    def get_file_url(self, obj):
        if not obj.file:
            return ''
        return safe_media_url(obj.file, request=self.context.get('request'), default='')
