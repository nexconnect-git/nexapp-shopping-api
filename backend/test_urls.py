"""
Minimal URL conf for test runs.

Only loads the apps under test. Excludes invoices/admin_urls/django_rq routes
that depend on optional production packages (xhtml2pdf, rq_scheduler, etc.).
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def health_check(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health_check),
    path("admin/", admin.site.urls),
    path("api/v1/", include("api_v1.urls")),
    path("api/auth/", include("accounts.urls")),
    path("api/vendors/", include("vendors.urls")),
    path("api/products/", include("products.urls")),
    path("api/orders/", include("orders.urls")),
    path("api/delivery/", include("delivery.urls")),
    path("api/notifications/", include("notifications.urls")),
]
