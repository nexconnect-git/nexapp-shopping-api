from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasAdminPermission
from notifications.actions import (
    DeleteAdminNotificationAction,
    GetAdminNotificationsAction,
    SendAdminNotificationAction,
)
from notifications.serializers import AdminNotificationSerializer, SendNotificationSerializer


class AdminNotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminNotificationListView(APIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'notifications.manage'

    def get(self, request):
        queryset = GetAdminNotificationsAction().execute(request.query_params)
        paginator = AdminNotificationPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(
            AdminNotificationSerializer(page, many=True).data
        )


class AdminSendNotificationView(APIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'notifications.manage'

    def post(self, request):
        serializer = SendNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notification, count = SendAdminNotificationAction().execute(
            request=request,
            data=serializer.validated_data,
        )
        if serializer.validated_data.get('user_id') and notification is None:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        if notification:
            return Response(
                AdminNotificationSerializer(notification).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {'status': f'Notification sent to {count} users.'},
            status=status.HTTP_201_CREATED,
        )


class AdminDeleteNotificationView(APIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'notifications.manage'

    def delete(self, request, pk):
        deleted = DeleteAdminNotificationAction().execute(request=request, notification_id=pk)
        if not deleted:
            return Response({'error': 'Notification not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
