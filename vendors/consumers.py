import json

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from vendors.data.workspace_repository import VendorWorkspaceRepository


class VendorOperationsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return
        vendor = await database_sync_to_async(VendorWorkspaceRepository().for_operations_socket)(user.pk)
        if not vendor:
            await self.close(code=4003)
            return

        self.group_name = f"vendor_ops_{vendor.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept(subprotocol="nexconnect.jwt")

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def vendor_event(self, event):
        await self.send(text_data=json.dumps({
            "event": event["event"],
            "payload": event["payload"],
        }))
