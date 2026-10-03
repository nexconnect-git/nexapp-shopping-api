import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from accounts.admin_access import allows, current_session_user
from accounts.actions.admin_actions import GetAdminStatsAction

class AdminStatsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'admin_stats'

        if not await self.has_access():
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
        if not await self.has_access():
            await self.close(code=4403)
            return
        stats = await self.get_stats()
        await self.send(text_data=json.dumps({
            'type': 'stats_update',
            'data': stats
        }))

    @database_sync_to_async
    def get_stats(self):
        current = current_session_user(self.scope['user'])
        return GetAdminStatsAction().execute(current) if allows(current, 'overview.view') else {}

    @database_sync_to_async
    def has_access(self):
        current=current_session_user(self.scope['user'])
        return allows(current, 'overview.view')
