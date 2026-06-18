import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasAdminPermission
from backend.actions.scheduled_task_actions import (
    CancelScheduledTaskAction,
    CreateScheduledTaskAction,
    ListScheduledTasksAction,
)


logger = logging.getLogger(__name__)


class AdminScheduledTaskListCreateView(APIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'automation.manage'

    def get(self, request):
        try:
            return Response(ListScheduledTasksAction().execute())
        except Exception as exc:
            logger.error(f'[AdminScheduledTaskListCreateView.get] {exc}')
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            payload, response_status = CreateScheduledTaskAction().execute(request.data)
            return Response(payload, status=response_status)
        except Exception as exc:
            logger.error(f'[AdminScheduledTaskListCreateView.post] {exc}')
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminScheduledTaskCancelView(APIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'automation.manage'

    def delete(self, request, job_id):
        try:
            payload, response_status = CancelScheduledTaskAction().execute(job_id)
            return Response(payload, status=response_status)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
