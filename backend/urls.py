from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from backend.health_views import health_live, health_ready
from backend.media_views import MediaFileView


urlpatterns = [
    path('health/', health_live),
    path('health/live/', health_live),
    path('health/ready/', health_ready),
    path('admin/', admin.site.urls),

    # v1 API
    path('api/v1/', include('api_v1.urls')),

    # Auth & core apps
    path('api/auth/', include('accounts.urls')),
    path('api/customer/', include('backend.customer_urls')),
    path('api/vendor/', include('backend.vendor_alias_urls')),
    path('api/vendors/', include('vendors.urls')),
    path('api/products/', include('products.urls')),
    path('api/orders/', include('orders.urls')),
    path('api/delivery/', include('delivery.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/support/', include('support.urls')),
    path('api/invoices/', include('invoices.urls')),
    path('api/files/', include('files.urls')),
    path('api/media/<path:path>/', MediaFileView.as_view(), name='media-file'),
    path('api/admin/', include('backend.admin_alias_urls')),
    path('api/admin/', include('backend.admin_urls')),

    # OpenAPI / Swagger
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

if settings.DEBUG or settings.ENABLE_DJANGO_RQ_DASHBOARD:
    urlpatterns.append(path('django-rq/', include('django_rq.urls')))

if settings.DEBUG and not settings.USE_S3:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
