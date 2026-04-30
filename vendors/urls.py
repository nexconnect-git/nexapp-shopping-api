from django.urls import path, include
from rest_framework.routers import DefaultRouter
from vendors import views

router = DefaultRouter()
router.register(r'products', views.VendorProductViewSet, basename='vendor-product')
router.register(r'coupons', views.VendorCouponViewSet, basename='vendor-coupon')

review_router = DefaultRouter()
review_router.register(r'reviews', views.VendorReviewViewSet, basename='vendor-review')

urlpatterns = [
    path('catalog-products/available/', views.VendorAvailableCatalogProductsView.as_view(), name='vendor-available-catalog-products'),
    path('catalog-products/available/<uuid:pk>/', views.VendorCatalogProductDetailView.as_view(), name='vendor-available-catalog-product-detail'),
    path('catalog-proposals/', views.VendorCatalogProposalListCreateView.as_view(), name='vendor-catalog-proposals'),
    path('products/from-catalog/', views.VendorCreateProductFromCatalogView.as_view(), name='vendor-product-from-catalog'),
    path('inherited-products/draft-batch/', views.VendorInheritedProductDraftBatchCreateView.as_view(), name='vendor-inherited-product-draft-batch'),
    path('inherited-products/submit/', views.VendorInheritedProductSubmitView.as_view(), name='vendor-inherited-product-submit'),
    path('inherited-products/', views.VendorInheritedProductListView.as_view(), name='vendor-inherited-products'),
    path('inherited-products/<uuid:pk>/', views.VendorInheritedProductDetailView.as_view(), name='vendor-inherited-product-detail'),
    path('inherited-products/<uuid:pk>/duplicate/', views.VendorInheritedProductDuplicateView.as_view(), name='vendor-inherited-product-duplicate'),
    path('inherited-products/<uuid:pk>/image-policy/', views.VendorInheritedProductImagePolicyView.as_view(), name='vendor-inherited-product-image-policy'),
    path('categories/', views.VendorCategoryListCreateView.as_view(), name='vendor-category-list-create'),
    path('categories/<uuid:pk>/subcategories/', views.VendorSubcategoryCreateView.as_view(), name='vendor-subcategory-create'),
    path('register/', views.VendorRegistrationView.as_view(), name='vendor-register'),
    path('list/', views.VendorListView.as_view(), name='vendor-list'),
    path('nearby/', views.NearbyVendorsView.as_view(), name='vendor-nearby'),
    path('dashboard/', views.VendorDashboardView.as_view(), name='vendor-dashboard'),
    path('operations/summary/', views.VendorOperationsSummaryView.as_view(), name='vendor-operations-summary'),
    path('analytics/', views.VendorAnalyticsView.as_view(), name='vendor-analytics'),
    path('wallet/transactions/', views.VendorWalletTransactionListView.as_view(), name='vendor-wallet-transactions'),
    path('payouts/', views.VendorPayoutListView.as_view(), name='vendor-payout-list'),
    path('payouts/<uuid:pk>/approve/', views.VendorPayoutApproveView.as_view(), name='vendor-payout-approve'),
    path('payouts/<uuid:pk>/decline/', views.VendorPayoutDeclineView.as_view(), name='vendor-payout-decline'),
    path('payouts/<uuid:pk>/verify-credit/', views.VendorPayoutVerifyCreditView.as_view(), name='vendor-payout-verify-credit'),
    path('profile/', views.VendorProfileView.as_view(), name='vendor-profile'),
    path('store-settings/', views.VendorStoreSettingsView.as_view(), name='vendor-store-settings'),
    path('live-orders/', views.VendorLiveOrdersView.as_view(), name='vendor-live-orders'),
    path('orders/', views.VendorOrdersView.as_view(), name='vendor-orders'),
    path('orders/<uuid:pk>/', views.VendorOrderDetailView.as_view(), name='vendor-order-detail'),
    path('orders/<uuid:pk>/status/', views.VendorUpdateOrderStatusView.as_view(), name='vendor-update-order-status'),
    path('orders/<uuid:pk>/accept/', views.VendorAcceptOrderView.as_view(), name='vendor-accept-order'),
    path('orders/<uuid:pk>/reject/', views.VendorRejectOrderView.as_view(), name='vendor-reject-order'),
    path('orders/<uuid:pk>/start-preparing/', views.VendorStartPreparingOrderView.as_view(), name='vendor-start-preparing-order'),
    path('orders/<uuid:pk>/mark-ready/', views.VendorMarkOrderReadyView.as_view(), name='vendor-mark-ready-order'),
    path('orders/<uuid:pk>/verify-pickup-otp/', views.VendorVerifyPickupOtpView.as_view(), name='vendor-verify-pickup-otp'),
    path('orders/<uuid:pk>/start-delivery-search/', views.VendorStartDeliverySearchView.as_view(), name='vendor-start-delivery-search'),
    path('orders/<uuid:pk>/cancel-delivery-search/', views.VendorCancelDeliverySearchView.as_view(), name='vendor-cancel-delivery-search'),
    path('store-status/', views.SetStoreStatusView.as_view(), name='vendor-store-status'),
    path('bulk-update-stock/', views.BulkUpdateStockView.as_view(), name='vendor-bulk-stock'),
    path('<uuid:pk>/', views.VendorDetailView.as_view(), name='vendor-detail'),
    path('<uuid:vendor_id>/', include(review_router.urls)),
    path('', include(router.urls)),
]
