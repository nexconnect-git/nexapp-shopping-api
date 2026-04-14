from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse

def health_check(_request):
    return JsonResponse({'status': 'ok'})

urlpatterns = [
    path('health/', health_check),
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/vendors/', include('vendors.urls')),
    path('api/products/', include('products.urls')),
    path('api/orders/', include('orders.urls')),
    path('api/delivery/', include('delivery.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/support/', include('support.urls')),
    path('api/invoices/', include('invoices.urls')),
    path('api/admin/', include('backend.admin_urls')),
    path('django-rq/', include('django_rq.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
