from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.actions import (
    GetUserNotificationsAction,
    MarkAllNotificationsReadAction,
    MarkNotificationReadAction,
)
from notifications.data import NotificationRepository
from notifications.serializers import NotificationSerializer
from vendors.helpers.public_vendor_helpers import StandardPagination


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = NotificationRepository.history_for_user(request.user, request.query_params)
        # Preserve the existing array contract for portals not yet migrated.
        if request.user.role != 'vendor' and 'page' not in request.query_params:
            return Response(NotificationSerializer(notifications, many=True).data)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(notifications, request)
        response = paginator.get_paginated_response(NotificationSerializer(page, many=True).data)
        response.data['unread_count'] = NotificationRepository.count_unread_for_user(request.user)
        return response


class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        notification = MarkNotificationReadAction().execute(pk, request.user)
        if not notification:
            return Response({'error': 'Notification not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(NotificationSerializer(notification).data)


class MarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        MarkAllNotificationsReadAction().execute(request.user)
        return Response({'status': 'All notifications marked as read.'})


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = NotificationRepository.count_unread_for_user(request.user)
        return Response({'unread_count': count, 'count': count})
