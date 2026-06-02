from django.urls import path
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.actions import GetCustomerHomeAction
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


class CustomerHomeView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(GetCustomerHomeAction().execute(request))


urlpatterns = [
    path("home/", CustomerHomeView.as_view(), name="customer-home"),
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
    path("checkout/preview/", CheckoutPreviewView.as_view(), name="customer-checkout-preview"),
    path("orders/", OrderListView.as_view(), name="customer-orders"),
    path("orders/create/", CreateOrderView.as_view(), name="customer-order-create"),
    path("orders/<uuid:pk>/", OrderDetailView.as_view(), name="customer-order-detail"),
    path("orders/<uuid:pk>/tracking/", OrderTrackingView.as_view(), name="customer-order-tracking"),
    path("orders/<uuid:pk>/rate/", SubmitOrderRatingView.as_view(), name="customer-order-rate"),
    path("orders/<uuid:pk>/reorder/", ReorderView.as_view(), name="customer-order-reorder"),
]
