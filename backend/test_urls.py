from django.urls import include, path

from backend.health_views import health_live, health_ready


urlpatterns = [
    path("health/", health_live),
    path("health/live/", health_live),
    path("health/ready/", health_ready),
    path("api/auth/", include("accounts.urls")),
    path("api/customer/", include("backend.customer_urls")),
    path("api/vendor/", include("backend.vendor_alias_urls")),
    path("api/vendors/", include("vendors.urls")),
    path("api/products/", include("products.urls")),
    path("api/orders/", include("orders.urls")),
    path("api/delivery/", include("delivery.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/support/", include("support.urls")),
    path("api/files/", include("files.urls")),
    path("api/admin/", include("backend.admin_alias_urls")),
]
