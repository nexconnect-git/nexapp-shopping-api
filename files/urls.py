from django.urls import path

from files.views import UploadedFileDetailView, UploadedFileListView, UploadedFileUploadView


urlpatterns = [
    path('', UploadedFileListView.as_view(), name='uploaded-file-list'),
    path('upload/', UploadedFileUploadView.as_view(), name='uploaded-file-upload'),
    path('<uuid:pk>/', UploadedFileDetailView.as_view(), name='uploaded-file-detail'),
]
