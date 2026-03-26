from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'reviews', views.DeliveryReviewViewSet, basename='delivery-review')

urlpatterns = [
    path('register/', views.DeliveryPartnerRegistrationView.as_view(), name='delivery-register'),
    path('dashboard/', views.DeliveryDashboardView.as_view(), name='delivery-dashboard'),
    path('available-orders/', views.AvailableOrdersView.as_view(), name='available-orders'),
    path('accept/<uuid:pk>/', views.AcceptDeliveryView.as_view(), name='accept-delivery'),
    path('confirm/<uuid:pk>/', views.ConfirmDeliveryView.as_view(), name='confirm-delivery'),
    path('update-status/<uuid:pk>/', views.UpdateDeliveryStatusView.as_view(), name='update-delivery-status'),
    path('update-location/', views.UpdateLocationView.as_view(), name='update-location'),
    path('history/', views.DeliveryHistoryView.as_view(), name='delivery-history'),
    path('earnings/', views.DeliveryEarningsView.as_view(), name='delivery-earnings'),
    path('', include(router.urls)),
]
