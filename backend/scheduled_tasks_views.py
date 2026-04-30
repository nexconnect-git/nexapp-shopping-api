"""
Admin views for managing scheduled background tasks via RQ Scheduler.
"""
import logging
from datetime import datetime, timezone
from django.utils import timezone as dj_timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsAdminRole

import django_rq

try:
    from rq_scheduler import Scheduler
except ModuleNotFoundError:
    Scheduler = None

try:
    from rq.job import Job
    from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry, DeferredJobRegistry
except (ImportError, ModuleNotFoundError):
    Job = None
    StartedJobRegistry = None
    FinishedJobRegistry = None
    FailedJobRegistry = None
    DeferredJobRegistry = None

logger = logging.getLogger(__name__)


def get_scheduler():
    if Scheduler is None:
        raise RuntimeError('rq_scheduler is not installed. Install it to manage scheduled jobs.')
    queue = django_rq.get_queue('default')
    return Scheduler(queue=queue, connection=queue.connection)


# Map of task identifiers to the actual importable function path
TASK_REGISTRY = {
    'generate_vendor_payouts': {
        'label': 'Process Vendor Payout',
        'description': 'Process a pending vendor payout record.',
        'func': 'notifications.scheduled_tasks.generate_vendor_payouts',
        'params': ['payout_id'],
        'icon': 'storefront',
        'category': 'payouts',
    },
    'generate_delivery_payouts': {
        'label': 'Process Delivery Payout',
        'description': 'Process a pending delivery partner payout.',
        'func': 'notifications.scheduled_tasks.generate_delivery_payouts',
        'params': ['payout_id'],
        'icon': 'two_wheeler',
        'category': 'payouts',
    },
    'generate_platform_report': {
        'label': 'Platform Sales Report',
        'description': 'Generate a platform-wide sales and orders statistics snapshot.',
        'func': 'notifications.scheduled_tasks.generate_platform_report',
        'params': [],
        'icon': 'bar_chart',
        'category': 'reports',
    },
    'send_bulk_notification': {
        'label': 'Send Bulk Notification',
        'description': 'Broadcast a notification to all users or a specific role group.',
        'func': 'notifications.scheduled_tasks.send_bulk_notification',
        'params': ['title', 'message', 'target'],
        'icon': 'campaign',
        'category': 'notifications',
    },
}


def _serialize_job(job, scheduled_time=None):
    """Convert an RQ Job instance to a JSON-safe dict."""
    func_name = ''
    task_key = ''
    try:
        func_name = job.func_name
        for key, meta in TASK_REGISTRY.items():
            if meta['func'] in func_name or key in func_name:
                task_key = key
                break
    except Exception:
        pass

    meta = TASK_REGISTRY.get(task_key, {})
    status_val = job.get_status()
    status_str = getattr(status_val, "value", status_val) if status_val else "scheduled"

    return {
        'id': job.id,
        'task_key': task_key,
        'label': meta.get('label', func_name),
        'icon': meta.get('icon', 'schedule'),
        'category': meta.get('category', 'other'),
        'args': list(job.args or []),
        'kwargs': dict(job.kwargs or {}),
        'scheduled_at': scheduled_time.isoformat() if scheduled_time else None,
        'enqueued_at': job.enqueued_at.isoformat() if job.enqueued_at else None,
        'status': status_str,
        'description': meta.get('description', ''),
    }


class AdminScheduledTaskListCreateView(APIView):
    """
    GET  /api/admin/scheduled-tasks/  — list all scheduled (pending) jobs
    POST /api/admin/scheduled-tasks/  — enqueue or schedule a new job
    """
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        try:
            scheduler = get_scheduler()
            jobs_with_times = scheduler.get_jobs(with_times=True)
            scheduler_serialized = []
            for job, scheduled_time in jobs_with_times:
                try:
                    scheduler_serialized.append(_serialize_job(job, scheduled_time))
                except Exception as e:
                    logger.warning(f"Could not serialize scheduler job {job.id}: {e}")

            queue = django_rq.get_queue('default')
            serialized = []

            # Initialize a set to avoid dupes across registries
            job_ids = set()
            
            # Add jobs sitting in the queue
            job_ids.update(queue.job_ids)
            
            if Job is None:
                raise RuntimeError('rq is not installed. Install it to inspect queue jobs.')

            # Add jobs from registries
            job_ids.update(StartedJobRegistry(queue=queue).get_job_ids())
            job_ids.update(FinishedJobRegistry(queue=queue).get_job_ids())
            job_ids.update(FailedJobRegistry(queue=queue).get_job_ids())
            job_ids.update(DeferredJobRegistry(queue=queue).get_job_ids())

            # Fetch them all
            jobs_list = Job.fetch_many(list(job_ids), connection=queue.connection)
            
            for job in jobs_list:
                if job is not None:
                    try:
                        # Find if this job is scheduled to get the exact scheduled time
                        scheduled_time = None
                        # Actually we can't easily correlate jobs_list scheduled times unless they are in jobs_with_times
                        # We'll rely on job.enqueued_at or get_status() internally
                        # But wait, scheduled jobs from rq-scheduler aren't inherently in standard registries unless queued
                        # Let's filter out ones we already grabbed from scheduler
                        serialized.append(_serialize_job(job))
                    except Exception as e:
                        logger.warning(f"Could not serialize queue job {job.id}: {e}")

            # Merge scheduler items with the ones we just added, keeping unique
            final_jobs = {}
            # Start with scheduled jobs (they have the `scheduled_at` correctly populated)
            for j in scheduler_serialized:
                final_jobs[j['id']] = j
            
            for j in serialized:
                if j['id'] not in final_jobs:
                    final_jobs[j['id']] = j

            # Also include available task definitions
            task_defs = [
                {
                    'key': key,
                    'label': meta['label'],
                    'description': meta['description'],
                    'icon': meta['icon'],
                    'category': meta['category'],
                    'params': meta['params'],
                }
                for key, meta in TASK_REGISTRY.items()
            ]

            return Response({'jobs': list(final_jobs.values()), 'task_definitions': task_defs})
        except Exception as e:
            logger.error(f"[AdminScheduledTaskListCreateView.get] {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        task_key = request.data.get('task_key')
        scheduled_time_str = request.data.get('scheduled_time')  # ISO datetime or None (immediate)
        repeat = request.data.get('repeat', None)  # None | integer (seconds interval)
        kwargs = request.data.get('kwargs', {})

        if task_key not in TASK_REGISTRY:
            return Response({'error': f'Unknown task: {task_key}'}, status=status.HTTP_400_BAD_REQUEST)

        meta = TASK_REGISTRY[task_key]

        # Dynamically import the task function
        module_path, func_name = meta['func'].rsplit('.', 1)
        import importlib
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)

        try:
            if scheduled_time_str:
                # Future scheduled job
                scheduled_time = datetime.fromisoformat(scheduled_time_str)
                if scheduled_time.tzinfo is None:
                    scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)

                scheduler = get_scheduler()
                if repeat:
                    # Repeating job (interval in seconds)
                    job = scheduler.schedule(
                        scheduled_time=scheduled_time,
                        func=func,
                        kwargs=kwargs,
                        interval=int(repeat),
                    )
                else:
                    job = scheduler.enqueue_at(scheduled_time, func, **kwargs)
            else:
                # Immediate execution
                queue = django_rq.get_queue('default')
                job = queue.enqueue(func, **kwargs)

            return Response({
                'id': job.id,
                'task_key': task_key,
                'label': meta['label'],
                'scheduled_at': scheduled_time_str,
                'status': 'scheduled' if scheduled_time_str else 'queued',
                'kwargs': kwargs,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"[AdminScheduledTaskListCreateView.post] {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminScheduledTaskCancelView(APIView):
    """
    DELETE /api/admin/scheduled-tasks/<job_id>/ — cancel a scheduled job
    """
    permission_classes = [IsAuthenticated, IsAdminRole]

    def delete(self, request, job_id):
        try:
            if Job is None:
                raise RuntimeError('rq is not installed. Install it to cancel queue jobs.')
            queue = django_rq.get_queue('default')
            try:
                job = Job.fetch(job_id, connection=queue.connection)
                job.delete()
            except Exception:
                pass
                
            scheduler = get_scheduler()
            if job_id in scheduler:
                scheduler.cancel(job_id)
            return Response({'cancelled': job_id}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
