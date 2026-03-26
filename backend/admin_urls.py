"""
URL patterns for /api/admin/ — admin-only endpoints.
All views enforce IsAdminRole permission internally.
"""
from django.urls import path
from accounts.views import (
    AdminCustomerListView,
    AdminCustomerDetailView,
    AdminUserStatsView,
)
from delivery.views import (
    AdminDeliveryPartnerListView,
    AdminDeliveryPartnerDetailView,
    AdminDeliveryPartnerApprovalView,
    AdminAssetListCreateView,
    AdminAssetDetailView,
)
from vendors.views import (
    AdminVendorListView,
    AdminVendorDetailView,
    AdminVendorStatusView,
    AdminVendorSalesReportView,
    # Onboarding
    AdminVendorOnboardView,
    AdminVendorOnboardingDetailView,
    AdminVendorKYCReviewView,
    AdminVendorBankDetailsView,
    AdminVendorBankVerifyView,
    AdminVendorDocumentListView,
    AdminVendorDocumentVerifyView,
    AdminVendorServiceableAreaView,
    AdminVendorServiceableAreaDetailView,
    AdminVendorHolidayView,
    AdminVendorHolidayDetailView,
    AdminVendorAuditLogView,
    AdminVendorPayoutListView,
    AdminVendorPayoutDetailView,
    AdminDeliveryPayoutListView,
    AdminDeliveryPayoutDetailView,
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
)
from notifications.views import (
    AdminNotificationListView,
    AdminSendNotificationView,
    AdminDeleteNotificationView,
)

urlpatterns = [
    # Platform stats
    path('stats/', AdminUserStatsView.as_view(), name='admin-stats'),

    # Customers
    path('customers/', AdminCustomerListView.as_view(), name='admin-customers'),
    path('customers/<uuid:pk>/', AdminCustomerDetailView.as_view(), name='admin-customer-detail'),

    # Vendors — CRUD
    path('vendors/', AdminVendorListView.as_view(), name='admin-vendors'),
    path('vendors/onboard/', AdminVendorOnboardView.as_view(), name='admin-vendor-onboard'),
    path('vendors/<uuid:pk>/', AdminVendorDetailView.as_view(), name='admin-vendor-detail'),
    path('vendors/<uuid:pk>/status/', AdminVendorStatusView.as_view(), name='admin-vendor-status'),
    # Onboarding workflow
    path('vendors/<uuid:pk>/onboarding/', AdminVendorOnboardingDetailView.as_view(), name='admin-vendor-onboarding'),
    path('vendors/<uuid:pk>/kyc-review/', AdminVendorKYCReviewView.as_view(), name='admin-vendor-kyc-review'),
    path('vendors/<uuid:pk>/bank/', AdminVendorBankDetailsView.as_view(), name='admin-vendor-bank'),
    path('vendors/<uuid:pk>/bank/verify/', AdminVendorBankVerifyView.as_view(), name='admin-vendor-bank-verify'),
    path('vendors/<uuid:pk>/documents/', AdminVendorDocumentListView.as_view(), name='admin-vendor-documents'),
    path('vendors/<uuid:pk>/documents/<uuid:doc_pk>/verify/', AdminVendorDocumentVerifyView.as_view(), name='admin-vendor-document-verify'),
    path('vendors/<uuid:pk>/serviceable-areas/', AdminVendorServiceableAreaView.as_view(), name='admin-vendor-serviceable-areas'),
    path('vendors/<uuid:pk>/serviceable-areas/<uuid:area_pk>/', AdminVendorServiceableAreaDetailView.as_view(), name='admin-vendor-serviceable-area-detail'),
    path('vendors/<uuid:pk>/holidays/', AdminVendorHolidayView.as_view(), name='admin-vendor-holidays'),
    path('vendors/<uuid:pk>/holidays/<uuid:holiday_pk>/', AdminVendorHolidayDetailView.as_view(), name='admin-vendor-holiday-detail'),
    path('vendors/<uuid:pk>/audit-logs/', AdminVendorAuditLogView.as_view(), name='admin-vendor-audit-logs'),
    path('vendors/<uuid:pk>/sales-report/', AdminVendorSalesReportView.as_view(), name='admin-vendor-sales-report'),
    path('payouts/vendors/', AdminVendorPayoutListView.as_view(), name='admin-vendor-payouts'),
    path('payouts/vendors/<uuid:pk>/', AdminVendorPayoutDetailView.as_view(), name='admin-vendor-payout-detail'),
    path('payouts/delivery/', AdminDeliveryPayoutListView.as_view(), name='admin-delivery-payouts'),
    path('payouts/delivery/<uuid:pk>/', AdminDeliveryPayoutDetailView.as_view(), name='admin-delivery-payout-detail'),

    # Delivery partners
    path('delivery-partners/', AdminDeliveryPartnerListView.as_view(), name='admin-delivery-partners'),
    path('delivery-partners/<uuid:pk>/', AdminDeliveryPartnerDetailView.as_view(), name='admin-delivery-partner-detail'),
    path('delivery-partners/<uuid:pk>/approve/', AdminDeliveryPartnerApprovalView.as_view(), name='admin-delivery-partner-approve'),

    # Categories
    path('categories/', AdminCategoryListCreateView.as_view(), name='admin-categories'),
    path('categories/<uuid:pk>/', AdminCategoryDetailView.as_view(), name='admin-category-detail'),

    # Products
    path('products/', AdminProductListCreateView.as_view(), name='admin-products'),
    path('products/<uuid:pk>/', AdminProductDetailView.as_view(), name='admin-product-detail'),

    # Orders
    path('orders/', AdminOrderListView.as_view(), name='admin-orders'),
    path('orders/<uuid:pk>/', AdminOrderDetailView.as_view(), name='admin-order-detail'),

    # Assets
    path('assets/', AdminAssetListCreateView.as_view(), name='admin-assets'),
    path('assets/<uuid:pk>/', AdminAssetDetailView.as_view(), name='admin-asset-detail'),

    # Notifications
    path('notifications/', AdminNotificationListView.as_view(), name='admin-notifications'),
    path('notifications/send/', AdminSendNotificationView.as_view(), name='admin-notifications-send'),
    path('notifications/<uuid:pk>/', AdminDeleteNotificationView.as_view(), name='admin-notification-delete'),
]
