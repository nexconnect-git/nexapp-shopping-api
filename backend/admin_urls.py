"""
URL patterns for /api/admin/ — admin-only endpoints.
All views enforce IsAdminRole permission internally.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from backend.scheduled_tasks_views import (
    AdminScheduledTaskListCreateView,
    AdminScheduledTaskCancelView,
)
from accounts.views import AdminUserViewSet, AdminStatsView
from vendors.views import (
    AdminVendorListView,
    AdminVendorDetailView,
    AdminVendorSalesReportView,
    AdminVendorOnboardView,
    AdminVendorStatusView,
    AdminVendorPayoutListView,
    AdminVendorPayoutDetailView,
    AdminVendorPayoutScheduleView,
    AdminVendorPayoutSendPaymentView,
    AdminVendorPayoutForcePaidView,
)
from delivery.views import (
    AdminDeliveryPartnerListView,
    AdminDeliveryPartnerDetailView,
    AdminDeliveryPartnerApprovalView,
    AdminDeliveryPartnerEarningsCalculationView,
    AdminAssetListCreateView,
    AdminAssetDetailView,
    AdminDeliveryPayoutListView,
    AdminDeliveryPayoutDetailView,
    AdminDeliveryPayoutScheduleView,
    AdminDeliveryPayoutSendPaymentView,
    AdminDeliveryPayoutForcePaidView,
)
from products.views import (
    AdminCategoryListCreateView,
    AdminCategoryDetailView,
    AdminProductListCreateView,
    AdminProductDetailView,
)
from orders.views import (
    AdminOrderListView,
    AdminOrderDetailView,
    AdminCouponViewSet,
    AdminOrderIssueListView,
    AdminOrderIssueDetailView,
    IssueMessageCreateView,
    AdminPlatformSettingView,
)
from notifications.views import (
    AdminNotificationListView,
    AdminSendNotificationView,
    AdminDeleteNotificationView,
)
from accounts.views.admin_customers import AdminCustomerViewSet

from products.views.admin_views import AdminProductViewSet

admin_router = DefaultRouter()
admin_router.register(r'coupons', AdminCouponViewSet, basename='admin-coupon')

admin_router.register(r'users', AdminUserViewSet, basename='admin-user')
admin_router.register(r'customers', AdminCustomerViewSet, basename='admin-customer')

admin_router.register(r'products', AdminProductViewSet, basename='admin-products')

urlpatterns = [
    path('', include(admin_router.urls)),
    
    # Dashboard summary statistics
    path('stats/', AdminStatsView.as_view(), name='admin-stats'),

    # Vendors — CRUD
    path('vendors/', AdminVendorListView.as_view(), name='admin-vendors'),
    path('vendors/onboard/', AdminVendorOnboardView.as_view(), name='admin-vendor-onboard'),
    path('vendors/<uuid:pk>/status/', AdminVendorStatusView.as_view(), name='admin-vendor-status'),
    path('vendors/<uuid:pk>/', AdminVendorDetailView.as_view(), name='admin-vendor-detail'),
    path('vendors/<uuid:pk>/sales-report/', AdminVendorSalesReportView.as_view(), name='admin-vendor-sales-report'),

    # Vendor payouts
    path('payouts/vendors/', AdminVendorPayoutListView.as_view(), name='admin-vendor-payouts'),
    path('payouts/vendors/<uuid:pk>/', AdminVendorPayoutDetailView.as_view(), name='admin-vendor-payout-detail'),
    path('payouts/vendors/<uuid:pk>/schedule/', AdminVendorPayoutScheduleView.as_view(), name='admin-vendor-payout-schedule'),
    path('payouts/vendors/<uuid:pk>/send-payment/', AdminVendorPayoutSendPaymentView.as_view(), name='admin-vendor-payout-send-payment'),
    path('payouts/vendors/<uuid:pk>/force-paid/', AdminVendorPayoutForcePaidView.as_view(), name='admin-vendor-payout-force-paid'),

    # Delivery partners
    path('delivery-partners/', AdminDeliveryPartnerListView.as_view(), name='admin-delivery-partners'),
    path('delivery-partners/<uuid:pk>/', AdminDeliveryPartnerDetailView.as_view(), name='admin-delivery-partner-detail'),
    path('delivery-partners/<uuid:pk>/calculate-earnings/', AdminDeliveryPartnerEarningsCalculationView.as_view(), name='admin-delivery-partner-earnings'),
    path('delivery-partners/<uuid:pk>/approve/', AdminDeliveryPartnerApprovalView.as_view(), name='admin-delivery-partner-approve'),

    # Delivery payouts
    path('payouts/delivery/', AdminDeliveryPayoutListView.as_view(), name='admin-delivery-payouts'),
    path('payouts/delivery/<uuid:pk>/', AdminDeliveryPayoutDetailView.as_view(), name='admin-delivery-payout-detail'),
    path('payouts/delivery/<uuid:pk>/schedule/', AdminDeliveryPayoutScheduleView.as_view(), name='admin-delivery-payout-schedule'),
    path('payouts/delivery/<uuid:pk>/send-payment/', AdminDeliveryPayoutSendPaymentView.as_view(), name='admin-delivery-payout-send-payment'),
    path('payouts/delivery/<uuid:pk>/force-paid/', AdminDeliveryPayoutForcePaidView.as_view(), name='admin-delivery-payout-force-paid'),

    # Categories
    path('categories/', AdminCategoryListCreateView.as_view(), name='admin-categories'),
    path('categories/<uuid:pk>/', AdminCategoryDetailView.as_view(), name='admin-category-detail'),

    # Products
    path('products/', AdminProductListCreateView.as_view(), name='admin-products'),
    path('products/<uuid:pk>/', AdminProductDetailView.as_view(), name='admin-product-detail'),

    # Orders
    path('settings/platform/', AdminPlatformSettingView.as_view(), name='admin-platform-settings'),
    path('orders/', AdminOrderListView.as_view(), name='admin-orders'),
    path('orders/<uuid:pk>/', AdminOrderDetailView.as_view(), name='admin-order-detail'),

    # Order Issues
    path('issues/', AdminOrderIssueListView.as_view(), name='admin-issues'),
    path('issues/<uuid:pk>/', AdminOrderIssueDetailView.as_view(), name='admin-issue-detail'),
    path('issues/<uuid:pk>/messages/', IssueMessageCreateView.as_view(), name='admin-issue-message'),

    # Assets
    path('assets/', AdminAssetListCreateView.as_view(), name='admin-assets'),
    path('assets/<uuid:pk>/', AdminAssetDetailView.as_view(), name='admin-asset-detail'),

    # Notifications
    path('notifications/', AdminNotificationListView.as_view(), name='admin-notifications'),
    path('notifications/send/', AdminSendNotificationView.as_view(), name='admin-notifications-send'),
    path('notifications/<uuid:pk>/', AdminDeleteNotificationView.as_view(), name='admin-notification-delete'),
    # Scheduled Tasks
    path('scheduled-tasks/', AdminScheduledTaskListCreateView.as_view(), name='admin-scheduled-tasks'),
    path('scheduled-tasks/<str:job_id>/', AdminScheduledTaskCancelView.as_view(), name='admin-scheduled-task-cancel'),
]
