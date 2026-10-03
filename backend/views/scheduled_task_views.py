import logging

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasAdminPermission
from backend.actions.scheduled_task_actions import (
    RetryScheduledTaskAction,
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
        except APIException:
            raise
        except Exception as exc:
            logger.error(f'[AdminScheduledTaskListCreateView.get] {exc}')
            return Response({'error': 'Background queue is unavailable. Check Redis and the scheduler, then retry.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    def post(self, request):
        try:
            payload, response_status = CreateScheduledTaskAction().execute(request.data, request=request)
            return Response(payload, status=response_status)
        except APIException:
            raise
        except Exception as exc:
            logger.error(f'[AdminScheduledTaskListCreateView.post] {exc}')
            return Response({'error': 'Background queue is unavailable. Check Redis and the scheduler, then retry.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class AdminScheduledTaskCancelView(APIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'automation.manage'

    def delete(self, request, job_id):
        try:
            payload, response_status = CancelScheduledTaskAction().execute(job_id, request=request)
            return Response(payload, status=response_status)
        except APIException:
            raise
        except Exception as exc:
            return Response({'error': 'Background queue is unavailable. Check Redis and the scheduler, then retry.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class AdminScheduledTaskRetryView(APIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'automation.manage'

    def post(self, request, job_id):
        try:
            return Response(RetryScheduledTaskAction().execute(job_id, request))
        except APIException:
            raise
        except Exception:
            return Response({'error': 'Background queue is unavailable.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
