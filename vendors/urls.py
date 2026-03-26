from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'products', views.VendorProductViewSet, basename='vendor-product')

review_router = DefaultRouter()
review_router.register(r'reviews', views.VendorReviewViewSet, basename='vendor-review')

urlpatterns = [
    path('register/', views.VendorRegistrationView.as_view(), name='vendor-register'),
    path('list/', views.VendorListView.as_view(), name='vendor-list'),
    path('nearby/', views.NearbyVendorsView.as_view(), name='vendor-nearby'),
    path('dashboard/', views.VendorDashboardView.as_view(), name='vendor-dashboard'),
    path('payouts/', views.VendorPayoutListView.as_view(), name='vendor-payout-list'),
    path('profile/', views.VendorProfileView.as_view(), name='vendor-profile'),
    path('orders/', views.VendorOrdersView.as_view(), name='vendor-orders'),
    path('orders/<uuid:pk>/status/', views.VendorUpdateOrderStatusView.as_view(), name='vendor-update-order-status'),
    path('<uuid:pk>/', views.VendorDetailView.as_view(), name='vendor-detail'),
    path('<uuid:vendor_id>/', include(review_router.urls)),
    path('', include(router.urls)),
]
