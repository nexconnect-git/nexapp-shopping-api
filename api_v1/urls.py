from django.urls import path
from api_v1.views import CartDeliveryQuoteV1View, NearbyVendorsV1View, VendorServiceabilityV1View

urlpatterns = [
    path("vendors/nearby/", NearbyVendorsV1View.as_view(), name="v1-nearby-vendors"),
    path("vendors/<uuid:pk>/serviceability/", VendorServiceabilityV1View.as_view(), name="v1-vendor-serviceability"),
    path("cart/delivery-quote/", CartDeliveryQuoteV1View.as_view(), name="v1-cart-delivery-quote"),
]
