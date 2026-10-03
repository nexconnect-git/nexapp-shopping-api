from django.utils import timezone
from rest_framework.exceptions import ValidationError

from notifications.data.scheduled_job_repository import ScheduledJobRepository


class SendScheduledBulkNotificationAction:
    def execute(self, title, message, target='all'):
        target = {'vendors': 'vendor', 'customers': 'customer'}.get(target, target)
        if target not in ('all', 'vendor', 'customer', 'delivery', 'admin'):
            raise ValidationError('Unknown notification target.')
        if not isinstance(title, str) or not isinstance(message, str) or not title.strip() or not message.strip() or len(title) > 200:
            raise ValidationError('A valid notification title and message are required.')
        return {'created': ScheduledJobRepository().broadcast(title.strip(), message.strip(), target), 'target': target}


class GeneratePlatformReportAction:
    def execute(self):
        return {**ScheduledJobRepository().platform_report(), 'generated_at': timezone.now().isoformat()}
