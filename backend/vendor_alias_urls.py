from django.urls import path

from vendors.views import (
    VendorAvailableCatalogProductsView,
    VendorCatalogProposalListCreateView,
    VendorCreateProductFromCatalogView,
    VendorDashboardView,
    VendorInheritedProductDetailView,
    VendorInheritedProductListView,
    VendorLiveOrdersView,
    VendorOrderDetailView,
    VendorOrdersView,
    VendorPayoutListView,
    VendorProfileView,
    VendorStoreSettingsView,
    VendorUpdateOrderStatusView,
)


urlpatterns = [
    path("dashboard/", VendorDashboardView.as_view(), name="vendor-alias-dashboard"),
    path("store/", VendorProfileView.as_view(), name="vendor-alias-store"),
    path("store/settings/", VendorStoreSettingsView.as_view(), name="vendor-alias-store-settings"),
    path("orders/live/", VendorLiveOrdersView.as_view(), name="vendor-alias-live-orders"),
    path("orders/", VendorOrdersView.as_view(), name="vendor-alias-orders"),
    path("orders/<uuid:pk>/", VendorOrderDetailView.as_view(), name="vendor-alias-order-detail"),
    path("orders/<uuid:pk>/status/", VendorUpdateOrderStatusView.as_view(), name="vendor-alias-order-status"),
    path("parent-catalog/search/", VendorAvailableCatalogProductsView.as_view(), name="vendor-alias-parent-catalog-search"),
    path("products/from-catalog/", VendorCreateProductFromCatalogView.as_view(), name="vendor-alias-products-from-catalog"),
    path("products/", VendorInheritedProductListView.as_view(), name="vendor-alias-products"),
    path("products/<uuid:pk>/", VendorInheritedProductDetailView.as_view(), name="vendor-alias-product-detail"),
    path("products/<uuid:pk>/inventory/", VendorInheritedProductDetailView.as_view(), name="vendor-alias-product-inventory"),
    path("catalog-requests/", VendorCatalogProposalListCreateView.as_view(), name="vendor-alias-catalog-requests"),
    path("payouts/", VendorPayoutListView.as_view(), name="vendor-alias-payouts"),
]
