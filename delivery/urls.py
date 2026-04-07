from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from vendors.views import (
    DeliveryPayoutListView,
    DeliveryPayoutApproveView,
    DeliveryPayoutDeclineView,
    DeliveryPayoutVerifyCreditView,
)

router = DefaultRouter()
router.register(r'reviews', views.DeliveryReviewViewSet, basename='delivery-review')

urlpatterns = [
    path('register/', views.DeliveryPartnerRegistrationView.as_view(), name='delivery-register'),
    path('dashboard/', views.DeliveryDashboardView.as_view(), name='delivery-dashboard'),
    path('available-orders/', views.AvailableOrdersView.as_view(), name='available-orders'),
    # Assignment-based flow
    path('requests/', views.PendingAssignmentRequestsView.as_view(), name='delivery-requests'),
    path('requests/<uuid:assignment_id>/accept/', views.AcceptAssignmentView.as_view(), name='accept-assignment'),
    path('requests/<uuid:assignment_id>/reject/', views.RejectAssignmentView.as_view(), name='reject-assignment'),
    path('<uuid:pk>/cancel-assignment/', views.CancelAssignmentView.as_view(), name='cancel-assignment'),
    # Legacy direct accept
    path('accept/<uuid:pk>/', views.AcceptDeliveryView.as_view(), name='accept-delivery'),
    path('confirm/<uuid:pk>/', views.ConfirmDeliveryView.as_view(), name='confirm-delivery'),
    path('update-status/<uuid:pk>/', views.UpdateDeliveryStatusView.as_view(), name='update-delivery-status'),
    path('update-location/', views.UpdateLocationView.as_view(), name='update-location'),
    path('set-availability/', views.SetAvailabilityView.as_view(), name='set-availability'),
    path('history/', views.DeliveryHistoryView.as_view(), name='delivery-history'),
    path('earnings/', views.DeliveryEarningsView.as_view(), name='delivery-earnings'),
    # Payout self-service
    path('payouts/', DeliveryPayoutListView.as_view(), name='delivery-payout-list'),
    path('payouts/<uuid:pk>/approve/', DeliveryPayoutApproveView.as_view(), name='delivery-payout-approve'),
    path('payouts/<uuid:pk>/decline/', DeliveryPayoutDeclineView.as_view(), name='delivery-payout-decline'),
    path('payouts/<uuid:pk>/verify-credit/', DeliveryPayoutVerifyCreditView.as_view(), name='delivery-payout-verify-credit'),
    path('', include(router.urls)),
]
