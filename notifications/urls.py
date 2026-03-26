from django.urls import path
from . import views

urlpatterns = [
    path('list/', views.NotificationListView.as_view(), name='notification-list'),
    path('<uuid:pk>/read/', views.MarkNotificationReadView.as_view(), name='notification-read'),
    path('mark-all-read/', views.MarkAllReadView.as_view(), name='notification-mark-all-read'),
    path('unread-count/', views.UnreadCountView.as_view(), name='notification-unread-count'),
    path('device-token/', views.DeviceTokenView.as_view(), name='device-token'),
]
