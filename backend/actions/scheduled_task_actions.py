import importlib
import logging
from datetime import datetime, timezone

from rest_framework import status

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
            'jobs': list(final_jobs.values()),
            'task_definitions': task_definitions(),
        }


class CreateScheduledTaskAction:
    def __init__(self, repository: ScheduledTaskRepository = None):
        self.repository = repository or ScheduledTaskRepository()

    def execute(self, data):
        task_key = data.get('task_key')
        if task_key not in TASK_REGISTRY:
            return {'error': f'Unknown task: {task_key}'}, status.HTTP_400_BAD_REQUEST

        scheduled_time_str = data.get('scheduled_time')
        repeat = data.get('repeat', None)
        kwargs = data.get('kwargs', {})
        meta = TASK_REGISTRY[task_key]
        module_path, func_name = meta['func'].rsplit('.', 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)

        if scheduled_time_str:
            scheduled_time = datetime.fromisoformat(scheduled_time_str)
            if scheduled_time.tzinfo is None:
                scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)
            if repeat:
                job = self.repository.schedule(scheduled_time, func, kwargs, repeat)
            else:
                job = self.repository.enqueue_at(scheduled_time, func, kwargs)
        else:
            job = self.repository.enqueue(func, kwargs)

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

    def execute(self, job_id):
        self.repository.cancel(job_id)
        return {'cancelled': job_id}, status.HTTP_200_OK
