from files.models import UploadedFile
from vendors.data.base import BaseRepository


class UploadedFileRepository(BaseRepository):
    def __init__(self):
        super().__init__(UploadedFile)

    def list_all(self):
        return self.all().select_related('uploaded_by').order_by('-created_at')

    def list_for_user(self, user):
        return (
            self.model.objects.filter(uploaded_by=user)
            .select_related('uploaded_by')
            .order_by('-created_at')
        )

    def get_by_client_upload_id(self, client_upload_id):
        if not client_upload_id:
            return None
        return self.model.objects.filter(client_upload_id=client_upload_id).select_related('uploaded_by').first()
