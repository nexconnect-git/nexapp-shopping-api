import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from accounts.actions.admin_actions import GetAdminStatsAction

class AdminStatsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'admin_stats'

        if not self.scope['user'].is_authenticated or self.scope['user'].role != 'admin':
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept(subprotocol=self.scope.get('ws_subprotocol'))

        stats = await self.get_stats()
        await self.send(text_data=json.dumps({
            'type': 'stats_update',
            'data': stats
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def update_stats(self, event):
        stats = await self.get_stats()
        await self.send(text_data=json.dumps({
            'type': 'stats_update',
            'data': stats
        }))

    @database_sync_to_async
    def get_stats(self):
        return GetAdminStatsAction().execute()
