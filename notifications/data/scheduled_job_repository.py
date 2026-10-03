from django.db.models import Sum

from accounts.models import User
from notifications.models import Notification
from orders.models import Order
from vendors.data.base import BaseRepository
from vendors.models import Vendor


class ScheduledJobRepository(BaseRepository):
    def __init__(self):
        super().__init__(Notification)

    def broadcast(self, title, message, target):
        users = User.objects.filter(is_active=True)
        if target != 'all':
            users = users.filter(role=target)
        rows = [Notification(user_id=user_id, title=title, message=message, notification_type='system') for user_id in users.values_list('pk', flat=True)]
        Notification.objects.bulk_create(rows, batch_size=500)
        return len(rows)

    def platform_report(self):
        return {'total_orders': Order.objects.count(), 'delivered_orders': Order.objects.filter(status='delivered').count(), 'total_revenue': str(Order.objects.filter(status='delivered', is_payment_verified=True).aggregate(amount=Sum('total'))['amount'] or 0), 'total_vendors': Vendor.objects.count(), 'total_users': User.objects.count()}
