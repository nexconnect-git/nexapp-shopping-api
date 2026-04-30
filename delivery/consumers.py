import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from orders.models import Order
from delivery.models import DeliveryPartner
from helpers.geo_helpers import calculate_eta_minutes

class DeliveryTrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.room_group_name = f'tracking_order_{self.order_id}'

        if not self.scope['user'].is_authenticated:
            await self.close()
            return

        has_perm = await self.check_tracking_access(self.order_id, self.scope['user'])
        if not has_perm:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept(subprotocol=self.scope.get('ws_subprotocol'))

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)

        # Expecting { 'action': 'update_location', 'lat': 12.x, 'lng': 77.x }
        if data.get('action') == 'update_location':
            can_publish = await self.can_publish_location(self.order_id, self.scope['user'])
            if not can_publish:
                return

            # Persist partner coordinates and get updated ETA
            partner_id, lat, lng, eta_minutes = await self.update_partner_location_and_eta(
                self.order_id, self.scope['user'], data.get('lat'), data.get('lng')
            )
            if partner_id is None or lat is None or lng is None:
                return

            # Broadcast location to everyone tracking this order
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'location_update',
                    'lat': lat,
                    'lng': lng,
                    'partner_id': partner_id,
                }
            )

            # Broadcast updated ETA if available
            if eta_minutes is not None:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {'type': 'eta_update', 'eta_minutes': eta_minutes}
                )

    async def location_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'location_update',
            'lat': event['lat'],
            'lng': event['lng'],
            'partner_id': event.get('partner_id'),
        }))

    async def eta_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'eta_update',
            'eta_minutes': event['eta_minutes'],
        }))

    @database_sync_to_async
    def update_partner_location_and_eta(self, order_id, user, lat, lng):
        """Persist partner GPS coords and return partner id + ETA."""
        if lat is None or lng is None:
            return None, None, None, None

        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            return None, None, None, None

        partner = None
        try:
            partner = user.delivery_profile
            DeliveryPartner.objects.filter(pk=partner.pk).update(
                current_latitude=lat, current_longitude=lng
            )
            order = Order.objects.select_related('vendor').get(pk=order_id)
            if (
                order.vendor.latitude and order.vendor.longitude
                and order.delivery_latitude and order.delivery_longitude
            ):
                eta_minutes = calculate_eta_minutes(
                    lat, lng,
                    float(order.vendor.latitude), float(order.vendor.longitude),
                    float(order.delivery_latitude), float(order.delivery_longitude),
                )
                return str(partner.user_id), lat, lng, eta_minutes
        except Exception:
            pass
        return (str(partner.user_id), lat, lng, None) if partner else (None, None, None, None)

    @database_sync_to_async
    def can_publish_location(self, order_id, user):
        try:
            order = Order.objects.select_related('assignment__accepted_partner__user').get(id=order_id)
            accepted_partner = getattr(order.assignment, 'accepted_partner', None)
            return bool(accepted_partner and accepted_partner.user == user)
        except Order.DoesNotExist:
            return False
        except Exception:
            return False

    @database_sync_to_async
    def check_tracking_access(self, order_id, user):
        try:
            order = Order.objects.get(id=order_id)
            # Admin can track any, Customer can track theirs, Vendor can track their store's, Partner can track what they are delivering
            if user.role == 'admin':
                return True
            if order.customer == user:
                return True
            if order.vendor.user == user:
                return True
            if hasattr(order, 'assignment') and order.assignment.accepted_partner and order.assignment.accepted_partner.user == user:
                return True
            return False
        except Order.DoesNotExist:
            return False
