from django.urls import path, include
from rest_framework.routers import DefaultRouter
from vendors import views

router = DefaultRouter()
router.register(r'products', views.VendorProductViewSet, basename='vendor-product')
router.register(r'coupons', views.VendorCouponViewSet, basename='vendor-coupon')

review_router = DefaultRouter()
review_router.register(r'reviews', views.VendorReviewViewSet, basename='vendor-review')

urlpatterns = [
    path('register/', views.VendorRegistrationView.as_view(), name='vendor-register'),
    path('list/', views.VendorListView.as_view(), name='vendor-list'),
    path('nearby/', views.NearbyVendorsView.as_view(), name='vendor-nearby'),
    path('dashboard/', views.VendorDashboardView.as_view(), name='vendor-dashboard'),
    path('payouts/', views.VendorPayoutListView.as_view(), name='vendor-payout-list'),
    path('payouts/<uuid:pk>/approve/', views.VendorPayoutApproveView.as_view(), name='vendor-payout-approve'),
    path('payouts/<uuid:pk>/decline/', views.VendorPayoutDeclineView.as_view(), name='vendor-payout-decline'),
    path('payouts/<uuid:pk>/verify-credit/', views.VendorPayoutVerifyCreditView.as_view(), name='vendor-payout-verify-credit'),
    path('profile/', views.VendorProfileView.as_view(), name='vendor-profile'),
    path('orders/', views.VendorOrdersView.as_view(), name='vendor-orders'),
    path('orders/<uuid:pk>/', views.VendorOrderDetailView.as_view(), name='vendor-order-detail'),
    path('orders/<uuid:pk>/status/', views.VendorUpdateOrderStatusView.as_view(), name='vendor-update-order-status'),
    path('orders/<uuid:pk>/verify-pickup-otp/', views.VendorVerifyPickupOtpView.as_view(), name='vendor-verify-pickup-otp'),
    path('orders/<uuid:pk>/start-delivery-search/', views.VendorStartDeliverySearchView.as_view(), name='vendor-start-delivery-search'),
    path('orders/<uuid:pk>/cancel-delivery-search/', views.VendorCancelDeliverySearchView.as_view(), name='vendor-cancel-delivery-search'),
    path('store-status/', views.SetStoreStatusView.as_view(), name='vendor-store-status'),
    path('bulk-update-stock/', views.BulkUpdateStockView.as_view(), name='vendor-bulk-stock'),
    path('<uuid:pk>/', views.VendorDetailView.as_view(), name='vendor-detail'),
    path('<uuid:vendor_id>/', include(review_router.urls)),
    path('', include(router.urls)),
]
