import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from orders.models import OrderIssue

class IssueChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.issue_id = self.scope['url_route']['kwargs']['issue_id']
        self.room_group_name = f'issue_{self.issue_id}'

        if not self.scope['user'].is_authenticated:
            await self.close()
            return

        has_perm = await self.check_issue_access(self.issue_id, self.scope['user'])
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

    async def chat_message(self, event):
        message_data = event['message']
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': message_data
        }))

    @database_sync_to_async
    def check_issue_access(self, issue_id, user):
        try:
            issue = OrderIssue.objects.get(id=issue_id)
            return user.role == 'admin' or issue.customer == user
        except OrderIssue.DoesNotExist:
            return False
