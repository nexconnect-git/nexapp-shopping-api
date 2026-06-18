"""ASGI config for the backend project."""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.config.settings')

django_asgi_app = get_asgi_application()

from backend.consumers import AdminStatsConsumer
from backend.middleware import JWTAuthMiddleware
from delivery.consumers import DeliveryTrackingConsumer
from orders.consumers import IssueChatConsumer
from vendors.consumers import VendorOperationsConsumer

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': JWTAuthMiddleware(
        URLRouter([
            path('ws/issues/<uuid:issue_id>/', IssueChatConsumer.as_asgi()),
            path('ws/delivery/<uuid:order_id>/tracking/', DeliveryTrackingConsumer.as_asgi()),
            path('ws/vendor/operations/', VendorOperationsConsumer.as_asgi()),
            path('ws/admin/stats/', AdminStatsConsumer.as_asgi()),
        ])
    ),
})
