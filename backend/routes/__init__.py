from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from backend.views import MediaFileView, health_live, health_ready


urlpatterns = [
    path('health/', health_live),
    path('health/live/', health_live),
    path('health/ready/', health_ready),
    path('admin/', admin.site.urls),
    path('api/v1/', include('api_v1.urls')),
    path('api/auth/', include('accounts.urls')),
    path('api/customer/', include('backend.routes.customer')),
    path('api/vendor/', include('backend.routes.vendor_alias')),
    path('api/vendors/', include('vendors.urls')),
    path('api/products/', include('products.urls')),
    path('api/orders/', include('orders.urls')),
    path('api/delivery/', include('delivery.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/support/', include('support.urls')),
    path('api/invoices/', include('invoices.urls')),
    path('api/files/', include('files.urls')),
    path('api/media/<path:path>/', MediaFileView.as_view(), name='media-file'),
    path('api/admin/', include('backend.routes.admin_alias')),
    path('api/admin/', include('backend.routes.admin')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

if settings.DEBUG or settings.ENABLE_DJANGO_RQ_DASHBOARD:
    urlpatterns.append(path('django-rq/', include('django_rq.urls')))

if settings.DEBUG and not settings.USE_S3:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
