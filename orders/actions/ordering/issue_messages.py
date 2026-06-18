import json

from django.db import transaction
from rest_framework.renderers import JSONRenderer

from backend.events import issue_message_added
from orders.actions.base import BaseAction
from orders.models import IssueMessage, OrderIssue
from orders.serializers import IssueMessageSerializer


class AddIssueMessageAction(BaseAction):
    @transaction.atomic
    def execute(self, issue_id, user, message_text) -> dict:
        is_admin = user.role == 'admin'
        try:
            if is_admin:
                issue = OrderIssue.objects.get(id=issue_id)
            else:
                issue = OrderIssue.objects.get(id=issue_id, customer=user)
        except OrderIssue.DoesNotExist:
            raise ValueError('Issue not found.')

        issue_message = IssueMessage.objects.create(
            issue=issue,
            sender=user,
            is_admin=is_admin,
            message=message_text,
        )

        if issue.status == 'open' and not is_admin:
            issue.status = 'in_review'
            issue.save(update_fields=['status', 'updated_at'])

        serializer = IssueMessageSerializer(issue_message)
        message_data = json.loads(JSONRenderer().render(serializer.data).decode('utf-8'))
        issue_message_added.send(sender=IssueMessage, issue_id=issue.id, message_data=message_data)
        return serializer.data
