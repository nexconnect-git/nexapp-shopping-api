import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from orders.models import Order
from delivery.models import DeliveryPartner

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

        await self.accept()

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
            lat = data.get('lat')
            lng = data.get('lng')
            
            # Broadcast to everyone tracking this order
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'location_update',
                    'lat': lat,
                    'lng': lng,
                    'partner_id': data.get('partner_id')
                }
            )
            
            # Optionally update DB status asynchronously here
            # await self.update_partner_location(data.get('partner_id'), lat, lng)

    async def location_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'location_update',
            'lat': event['lat'],
            'lng': event['lng'],
            'partner_id': event.get('partner_id')
        }))

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
