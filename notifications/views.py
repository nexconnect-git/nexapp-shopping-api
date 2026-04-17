"""
API views for the ``notifications`` app.

Endpoints covered:
  - Notification list, mark-read, mark-all-read, unread count
  - Device token registration for push notifications
  - Admin: list, send (targeted or broadcast), and delete notifications
"""

from django.db.models import Q

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdminRole
from notifications.models import DeviceToken, Notification
from notifications.serializers import (
    AdminNotificationSerializer,
    NotificationSerializer,
    SendNotificationSerializer,
)


class NotificationListView(APIView):
    """GET /api/notifications/ — list all notifications for the authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return all notifications for the current user.

        Args:
            request: Authenticated DRF request.

        Returns:
            200 with a list of notification objects.
        """
        notifications = Notification.objects.filter(user=request.user)
        return Response(NotificationSerializer(notifications, many=True).data)


class MarkNotificationReadView(APIView):
    """PATCH /api/notifications/<pk>/read/ — mark a single notification as read."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        """Mark a specific notification as read.

        Args:
            request: Authenticated DRF request.
            pk: UUID primary key of the notification.

        Returns:
            200 with updated notification data, or 404.
        """
        try:
            notification = Notification.objects.get(pk=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response(
                {"error": "Notification not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)


class MarkAllReadView(APIView):
    """POST /api/notifications/mark-all-read/ — mark all unread notifications as read."""

    permission_classes = [IsAuthenticated]

    def post(self, request):  # noqa: ARG002
        """Bulk-update all unread notifications for the current user.

        Args:
            request: Authenticated DRF request.

        Returns:
            200 with a confirmation message.
        """
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"status": "All notifications marked as read."})


class UnreadCountView(APIView):
    """GET /api/notifications/unread-count/ — return the unread notification count."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return the number of unread notifications for the current user.

        Args:
            request: Authenticated DRF request.

        Returns:
            200 with ``{"unread_count": <int>}``.
        """
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread_count": count})


class DeviceTokenView(APIView):
    """POST /api/notifications/device-token/ — register or update an FCM push token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Upsert a device token for the authenticated user.

        Args:
            request: Authenticated DRF request with ``token`` and optional
                ``platform`` (default: ``'web'``).

        Returns:
            201 if the token was newly created, 200 if updated.
            400 if ``token`` is missing.
        """
        token = request.data.get("token")
        platform = request.data.get("platform", "web")
        if not token:
            return Response(
                {"error": "token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _, created = DeviceToken.objects.update_or_create(
            token=token,
            defaults={"user": request.user, "platform": platform},
        )
        return Response(
            {"status": "token registered"},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Admin views
# ---------------------------------------------------------------------------

class AdminNotificationPagination(PageNumberPagination):
    """Default pagination for admin notification list views."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminNotificationListView(APIView):
    """GET /api/admin/notifications/ — list all notifications (admin only)."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        """Return a paginated, optionally filtered list of all notifications.

        Query params:
            search: Filter by title, message, or username.
            type: Filter by notification type.
            is_read: Filter by read status (true/false).

        Args:
            request: Authenticated admin DRF request.

        Returns:
            Paginated list of notification objects.
        """
        qs = Notification.objects.select_related("user").order_by("-created_at")

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(message__icontains=search)
                | Q(user__username__icontains=search)
            )

        notification_type = request.query_params.get("notification_type") or request.query_params.get("type")
        if notification_type:
            qs = qs.filter(notification_type=notification_type)

        is_read = request.query_params.get("is_read")
        if is_read is not None:
            qs = qs.filter(is_read=is_read.lower() == "true")

        paginator = AdminNotificationPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            AdminNotificationSerializer(page, many=True).data
        )


class AdminSendNotificationView(APIView):
    """POST /api/admin/notifications/send/ — send a targeted or broadcast notification."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        """Create and deliver a notification to one user or all users.

        When ``user_id`` is provided the notification is sent to that user only.
        When omitted, the notification is broadcast to every user via
        ``bulk_create``.

        Args:
            request: Authenticated admin DRF request with notification payload.

        Returns:
            201 with the created notification (targeted) or a count summary
            (broadcast). 404 if the specified user is not found.
        """
        serializer = SendNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user_id = data.get("user_id")
        if user_id:
            try:
                recipient = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return Response(
                    {"error": "User not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            notification = Notification.objects.create(
                user=recipient,
                title=data["title"],
                message=data["message"],
                notification_type=data["notification_type"],
            )
            return Response(
                AdminNotificationSerializer(notification).data,
                status=status.HTTP_201_CREATED,
            )

        # Broadcast — optionally filtered by role
        role = data.get("role")
        qs = User.objects.filter(role=role) if role else User.objects.all()
        notifications = [
            Notification(
                user=user,
                title=data["title"],
                message=data["message"],
                notification_type=data["notification_type"],
            )
            for user in qs
        ]
        Notification.objects.bulk_create(notifications)
        return Response(
            {"status": f"Notification sent to {len(notifications)} users."},
            status=status.HTTP_201_CREATED,
        )


class AdminDeleteNotificationView(APIView):
    """DELETE /api/admin/notifications/<pk>/ — delete a notification."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def delete(self, request, pk):  # noqa: ARG002
        """Delete a single notification.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the notification.

        Returns:
            204 on success, or 404.
        """
        try:
            notification = Notification.objects.get(pk=pk)
        except Notification.DoesNotExist:
            return Response(
                {"error": "Notification not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        notification.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
