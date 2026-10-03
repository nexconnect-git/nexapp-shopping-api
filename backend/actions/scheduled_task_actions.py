import importlib
import logging
from datetime import datetime, timezone

from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from uuid import UUID

from accounts.actions.audit_actions import CreateAdminAuditLogAction
from accounts.admin_access import allows

from backend.data import ScheduledTaskRepository
from helpers.scheduled_task_helpers import TASK_REGISTRY, serialize_job, task_definitions


logger = logging.getLogger(__name__)


class ListScheduledTasksAction:
    def __init__(self, repository: ScheduledTaskRepository = None):
        self.repository = repository or ScheduledTaskRepository()

    def execute(self):
        scheduler_serialized = []
        for job, scheduled_time in self.repository.get_scheduler_jobs_with_times():
            try:
                scheduler_serialized.append(serialize_job(job, scheduled_time))
            except Exception as exc:
                logger.warning(f'Could not serialize scheduler job {job.id}: {exc}')

        queue_serialized = []
        for job in self.repository.get_queue_jobs():
            if job is None:
                continue
            try:
                queue_serialized.append(serialize_job(job))
            except Exception as exc:
                logger.warning(f'Could not serialize queue job {job.id}: {exc}')

        final_jobs = {}
        for job in scheduler_serialized:
            final_jobs[job['id']] = job
        for job in queue_serialized:
            if job['id'] not in final_jobs:
                final_jobs[job['id']] = job

        return {
            'jobs': sorted(final_jobs.values(), key=lambda job: job['enqueued_at'] or job['scheduled_at'] or '', reverse=True),
            'queue': {'state': 'connected', 'name': 'default', 'scope': 'Up to 500 retained queue records plus scheduled jobs; Redis reachable, worker execution not verified.'},
            'task_definitions': task_definitions(),
        }


class CreateScheduledTaskAction:
    def __init__(self, repository: ScheduledTaskRepository = None):
        self.repository = repository or ScheduledTaskRepository()

    def execute(self, data, request=None):
        task_key = data.get('task_key')
        if task_key not in TASK_REGISTRY:
            return {'error': f'Unknown task: {task_key}'}, status.HTTP_400_BAD_REQUEST

        scheduled_time_str = data.get('scheduled_time')
        repeat = data.get('repeat', None)
        kwargs = data.get('kwargs', {})
        meta = TASK_REGISTRY[task_key]
        permission = {'payouts': 'finance.manage', 'notifications': 'notifications.manage'}.get(meta['category'])
        if request is not None and permission and not allows(request.user, permission):
            raise PermissionDenied(f'{permission} is also required for this task.')
        if not isinstance(kwargs, dict) or set(kwargs) - set(meta['params']):
            raise ValidationError('Task parameters must match the registered task definition.')
        if any(kwargs.get(key) in (None, '') for key in meta['params']):
            raise ValidationError('Every listed task parameter is required.')
        for key in ('payout_id', 'user_id'):
            if key in kwargs:
                try:
                    UUID(str(kwargs[key]))
                except (ValueError, TypeError):
                    raise ValidationError(f'{key} must be a valid UUID.')
        for key in ('warning_minutes', 'failed_payment_age_minutes', 'limit'):
            if key in kwargs:
                try:
                    value = int(kwargs[key])
                except (ValueError, TypeError):
                    raise ValidationError(f'{key} must be an integer.')
                if not 1 <= value <= 1440:
                    raise ValidationError(f'{key} must be between 1 and 1440.')
                kwargs[key] = value
        if 'target' in kwargs and kwargs['target'] not in ('all', 'customer', 'vendor', 'delivery', 'admin'):
            raise ValidationError('Unknown notification target.')
        if 'transaction_ref' in kwargs and (not str(kwargs['transaction_ref']).strip() or len(str(kwargs['transaction_ref'])) > 100):
            raise ValidationError('A valid external payment reference is required.')
        for key in ('title', 'message'):
            if key in kwargs and (not isinstance(kwargs[key], str) or not kwargs[key].strip() or (key == 'title' and len(kwargs[key]) > 200)):
                raise ValidationError(f'{key} must be a valid non-empty string; titles are limited to 200 characters.')
        if repeat is not None and (type(repeat) is not int or not 60 <= repeat <= 604800 or not scheduled_time_str):
            raise ValidationError('Repeat requires a scheduled time and an interval between 60 seconds and one week.')
        module_path, func_name = meta['func'].rsplit('.', 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)

        if scheduled_time_str:
            try:
                scheduled_time = datetime.fromisoformat(scheduled_time_str)
            except (ValueError, TypeError):
                raise ValidationError('Scheduled time must be a valid ISO datetime.')
            if scheduled_time.tzinfo is None:
                scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)
            if scheduled_time <= datetime.now(timezone.utc):
                raise ValidationError('Scheduled time must be in the future.')
            if repeat:
                job = self.repository.schedule(scheduled_time, func, kwargs, repeat)
            else:
                job = self.repository.enqueue_at(scheduled_time, func, kwargs)
        else:
            job = self.repository.enqueue(func, kwargs)

        if request is not None:
            CreateAdminAuditLogAction().execute(request=request, action='create', entity_type='scheduled_job', entity_id=str(job.id), summary=f'Scheduled {task_key}.', metadata={'task': task_key, 'scheduled_at': scheduled_time_str, 'repeat': repeat, 'parameters': kwargs})
        return {
            'id': job.id,
            'task_key': task_key,
            'label': meta['label'],
            'scheduled_at': scheduled_time_str,
            'status': 'scheduled' if scheduled_time_str else 'queued',
            'kwargs': kwargs,
        }, status.HTTP_201_CREATED


class CancelScheduledTaskAction:
    def __init__(self, repository: ScheduledTaskRepository = None):
        self.repository = repository or ScheduledTaskRepository()

    def execute(self, job_id, request=None):
        job = self.repository.job(job_id)
        meta = next((definition for definition in TASK_REGISTRY.values() if definition['func'] == job.func_name), None)
        if meta is None:
            raise ValidationError('Only registered admin tasks can be cancelled here.')
        permission = {'payouts': 'finance.manage', 'notifications': 'notifications.manage'}.get(meta['category'])
        if request is not None and permission and not allows(request.user, permission):
            raise PermissionDenied(f'{permission} is also required for this task.')
        self.repository.cancel(job_id)
        if request is not None:
            CreateAdminAuditLogAction().execute(request=request, action='update', entity_type='scheduled_job', entity_id=job_id, summary='Cancelled a queued or scheduled job.')
        return {'cancelled': job_id}, status.HTTP_200_OK


class RetryScheduledTaskAction:
    def __init__(self, repository=None):
        self.repository = repository or ScheduledTaskRepository()

    def execute(self, job_id, request):
        job = self.repository.job(job_id)
        task_key = next((key for key, meta in TASK_REGISTRY.items() if meta['func'] == job.func_name), None)
        if not task_key:
            raise ValidationError('Only registered admin tasks can be retried here.')
        category = TASK_REGISTRY[task_key]['category']
        permission = {'payouts': 'finance.manage', 'notifications': 'notifications.manage'}.get(category)
        if permission and not allows(request.user, permission):
            raise PermissionDenied()
        retried = self.repository.retry(job_id)
        CreateAdminAuditLogAction().execute(request=request, action='update', entity_type='scheduled_job', entity_id=job_id, summary='Retried a failed task.', metadata={'task': task_key})
        return serialize_job(retried)
