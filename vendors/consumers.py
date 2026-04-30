import json

from channels.generic.websocket import AsyncWebsocketConsumer


class VendorOperationsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return
        try:
            vendor = user.vendor_profile
        except Exception:
            await self.close(code=4003)
            return
        if vendor.status != "approved":
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
