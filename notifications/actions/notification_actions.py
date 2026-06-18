from accounts.actions.audit_actions import CreateAdminAuditLogAction
from accounts.data.user_repository import UserRepository
from notifications.data import NotificationRepository
from notifications.helpers import parse_optional_bool
from notifications.models import Notification


class GetUserNotificationsAction:
    def __init__(self, repository: NotificationRepository = None):
        self.repository = repository or NotificationRepository()

    def execute(self, user):
        return self.repository.filter_for_user(user)


class MarkNotificationReadAction:
    def __init__(self, repository: NotificationRepository = None):
        self.repository = repository or NotificationRepository()

    def execute(self, notification_id, user):
        notification = self.repository.get_by_id_and_user(notification_id, user)
        if not notification:
            return None
        return self.repository.mark_read(notification)


class MarkAllNotificationsReadAction:
    def __init__(self, repository: NotificationRepository = None):
        self.repository = repository or NotificationRepository()

    def execute(self, user) -> int:
        return self.repository.mark_all_read_for_user(user)


class GetAdminNotificationsAction:
    def __init__(self, repository: NotificationRepository = None):
        self.repository = repository or NotificationRepository()

    def execute(self, query_params):
        notification_type = query_params.get('notification_type') or query_params.get('type')
        return self.repository.filter_admin(
            search=query_params.get('search'),
            notification_type=notification_type,
            is_read=parse_optional_bool(query_params.get('is_read')),
        )


class SendAdminNotificationAction:
    def __init__(
        self,
        notification_repository: NotificationRepository = None,
        user_repository: UserRepository = None,
        audit_action: CreateAdminAuditLogAction = None,
    ):
        self.notifications = notification_repository or NotificationRepository()
        self.users = user_repository or UserRepository()
        self.audit_action = audit_action or CreateAdminAuditLogAction()

    def execute(self, request, data: dict):
        user_id = data.get('user_id')
        if user_id:
            recipient = self.users.get_by_id(str(user_id))
            if not recipient:
                return None, 0
            notification = self.notifications.create(
                user=recipient,
                title=data['title'],
                message=data['message'],
                notification_type=data['notification_type'],
            )
            self.audit_action.execute(
                request=request,
                action='notification',
                entity_type='notification',
                entity_id=str(notification.id),
                summary=f"Sent notification '{notification.title}' to {recipient.username}.",
                metadata={
                    'user_id': str(recipient.id),
                    'notification_type': notification.notification_type,
                },
            )
            return notification, 1

        role = data.get('role')
        users = self.users.filter(role=role) if role else self.users.get_all()
        notifications = [
            Notification(
                user=user,
                title=data['title'],
                message=data['message'],
                notification_type=data['notification_type'],
            )
            for user in users
        ]
        self.notifications.bulk_create(notifications)
        self.audit_action.execute(
            request=request,
            action='notification',
            entity_type='notification_broadcast',
            summary=f"Broadcast notification '{data['title']}' to {len(notifications)} users.",
            metadata={
                'role': role or 'all',
                'count': len(notifications),
                'notification_type': data['notification_type'],
            },
        )
        return None, len(notifications)


class DeleteAdminNotificationAction:
    def __init__(
        self,
        notification_repository: NotificationRepository = None,
        audit_action: CreateAdminAuditLogAction = None,
    ):
        self.notifications = notification_repository or NotificationRepository()
        self.audit_action = audit_action or CreateAdminAuditLogAction()

    def execute(self, request, notification_id) -> bool:
        notification = self.notifications.get_by_id(notification_id)
        if not notification:
            return False
        self.audit_action.execute(
            request=request,
            action='delete',
            entity_type='notification',
            entity_id=str(notification.id),
            summary=f"Deleted notification '{notification.title}'.",
            metadata={'notification_type': notification.notification_type},
        )
        self.notifications.delete(notification)
        return True
