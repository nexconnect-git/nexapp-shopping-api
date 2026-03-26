from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q

from .models import Notification, DeviceToken
from .serializers import NotificationSerializer, AdminNotificationSerializer, SendNotificationSerializer
from accounts.permissions import IsAdminRole
from accounts.models import User



class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(user=request.user)
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)


class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
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
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True
        )
        return Response({"status": "All notifications marked as read."})


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread_count": count})


class DeviceTokenView(APIView):
    """POST /api/notifications/device-token/  — register/update FCM token"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get('token')
        platform = request.data.get('platform', 'web')
        if not token:
            return Response({'error': 'token is required'}, status=status.HTTP_400_BAD_REQUEST)

        obj, created = DeviceToken.objects.update_or_create(
            token=token,
            defaults={'user': request.user, 'platform': platform}
        )
        return Response({'status': 'token registered'}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)



# ── Admin views ────────────────────────────────────────────────────────────────

class AdminNotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminNotificationListView(APIView):
    """GET /api/admin/notifications/ — list all notifications (admin only)."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        qs = Notification.objects.select_related('user').order_by('-created_at')

        search = request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(message__icontains=search) |
                Q(user__username__icontains=search)
            )

        notification_type = request.query_params.get('type')
        if notification_type:
            qs = qs.filter(notification_type=notification_type)

        is_read = request.query_params.get('is_read')
        if is_read is not None:
            qs = qs.filter(is_read=is_read.lower() == 'true')

        paginator = AdminNotificationPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = AdminNotificationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminSendNotificationView(APIView):
    """POST /api/admin/notifications/send/ — send a notification."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        serializer = SendNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user_id = data.get('user_id')
        if user_id:
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            notification = Notification.objects.create(
                user=user,
                title=data['title'],
                message=data['message'],
                notification_type=data['notification_type'],
            )
            return Response(
                AdminNotificationSerializer(notification).data,
                status=status.HTTP_201_CREATED,
            )
        else:
            # Broadcast to all users
            users = User.objects.all()
            notifications = [
                Notification(
                    user=u,
                    title=data['title'],
                    message=data['message'],
                    notification_type=data['notification_type'],
                )
                for u in users
            ]
            Notification.objects.bulk_create(notifications)
            return Response(
                {'status': f'Notification sent to {len(notifications)} users.'},
                status=status.HTTP_201_CREATED,
            )


class AdminDeleteNotificationView(APIView):
    """DELETE /api/admin/notifications/<pk>/ — delete a notification."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def delete(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk)
        except Notification.DoesNotExist:
            return Response(
                {'error': 'Notification not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        notification.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
