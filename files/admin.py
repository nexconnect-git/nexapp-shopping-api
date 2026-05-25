from django.contrib import admin

from files.models import UploadedFile


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'use_of_image', 'content_type', 'size', 'uploaded_by', 'created_at')
    search_fields = ('original_filename', 'content_type', 'use_of_image', 'uploaded_by__username')
    list_filter = ('use_of_image', 'content_type', 'created_at')
    readonly_fields = ('created_at',)
