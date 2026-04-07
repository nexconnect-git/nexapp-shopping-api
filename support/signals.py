from django.dispatch import receiver
from backend.events import issue_message_added
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@receiver(issue_message_added)
def broadcast_issue_message(sender, issue_id, message_data, **kwargs):
    """
    Broadcasts a new issue message to the WebSocket group using django channels.
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'issue_{issue_id}',
        {
            'type': 'chat_message',
            'message': message_data
        }
    )
