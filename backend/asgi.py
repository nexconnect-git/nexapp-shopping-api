"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

django_asgi_app = get_asgi_application()

from backend.middleware import JWTAuthMiddleware
from orders.consumers import IssueChatConsumer
from delivery.consumers import DeliveryTrackingConsumer
from backend.consumers import AdminStatsConsumer
from vendors.consumers import VendorOperationsConsumer

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        URLRouter([
            path("ws/issues/<uuid:issue_id>/", IssueChatConsumer.as_asgi()),
            path("ws/delivery/<uuid:order_id>/tracking/", DeliveryTrackingConsumer.as_asgi()),
            path("ws/vendor/operations/", VendorOperationsConsumer.as_asgi()),
            path("ws/admin/stats/", AdminStatsConsumer.as_asgi()),
        ])
    ),
})
