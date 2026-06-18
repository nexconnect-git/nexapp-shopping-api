from django.urls import path

from backend.views import (
    CustomerActiveOrderView,
    CustomerBestCouponView,
    CustomerBuyAgainView,
    CustomerCartSuggestionsView,
    CustomerCheckoutSlotsView,
    CustomerExploreView,
    CustomerHomeView,
    CustomerOrderConfirmationView,
    CustomerServiceabilityView,
)
from orders.views import (
    AddToCartView,
    CartView,
    CheckoutPreviewView,
    ClearCartView,
    CreateOrderView,
    OrderDetailView,
    OrderListView,
    OrderTrackingView,
    ReorderView,
    ReplaceCartView,
    SubmitOrderRatingView,
    UpdateCartItemView,
)
from products.views import (
    CategoryListView,
    ProductDetailView,
    ProductSearchByLocationView,
)
from vendors.views import NearbyVendorsView, VendorDetailView, VendorListView


urlpatterns = [
    path("home/", CustomerHomeView.as_view(), name="customer-home"),
    path("location/serviceability/", CustomerServiceabilityView.as_view(), name="customer-location-serviceability"),
    path("explore/", CustomerExploreView.as_view(), name="customer-explore"),
    path("buy-again/", CustomerBuyAgainView.as_view(), name="customer-buy-again"),
    path("stores/nearby/", NearbyVendorsView.as_view(), name="customer-stores-nearby"),
    path("stores/", VendorListView.as_view(), name="customer-stores"),
    path("stores/<uuid:pk>/", VendorDetailView.as_view(), name="customer-store-detail"),
    path("stores/<uuid:pk>/products/", VendorDetailView.as_view(), name="customer-store-products"),
    path("categories/", CategoryListView.as_view(), name="customer-categories"),
    path("search/", ProductSearchByLocationView.as_view(), name="customer-search"),
    path("products/<uuid:pk>/", ProductDetailView.as_view(), name="customer-product-detail"),
    path("cart/", CartView.as_view(), name="customer-cart"),
    path("cart/items/", AddToCartView.as_view(), name="customer-cart-add"),
    path("cart/items/<uuid:pk>/", UpdateCartItemView.as_view(), name="customer-cart-item"),
    path("cart/replace/", ReplaceCartView.as_view(), name="customer-cart-replace"),
    path("cart/clear/", ClearCartView.as_view(), name="customer-cart-clear"),
    path("cart/suggestions/", CustomerCartSuggestionsView.as_view(), name="customer-cart-suggestions"),
    path("cart/apply-best-coupon/", CustomerBestCouponView.as_view(), name="customer-cart-best-coupon"),
    path("checkout/preview/", CheckoutPreviewView.as_view(), name="customer-checkout-preview"),
    path("checkout/slots/", CustomerCheckoutSlotsView.as_view(), name="customer-checkout-slots"),
    path("orders/", OrderListView.as_view(), name="customer-orders"),
    path("orders/active/", CustomerActiveOrderView.as_view(), name="customer-order-active"),
    path("orders/create/", CreateOrderView.as_view(), name="customer-order-create"),
    path("orders/<uuid:pk>/", OrderDetailView.as_view(), name="customer-order-detail"),
    path("orders/<uuid:pk>/confirmation/", CustomerOrderConfirmationView.as_view(), name="customer-order-confirmation"),
    path("orders/<uuid:pk>/tracking/", OrderTrackingView.as_view(), name="customer-order-tracking"),
    path("orders/<uuid:pk>/rate/", SubmitOrderRatingView.as_view(), name="customer-order-rate"),
    path("orders/<uuid:pk>/reorder/", ReorderView.as_view(), name="customer-order-reorder"),
]
