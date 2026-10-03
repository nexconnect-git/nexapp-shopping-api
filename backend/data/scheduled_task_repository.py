import django_rq
from rest_framework.exceptions import NotFound, ValidationError

try:
    from rq.job import Job
    from rq.registry import CanceledJobRegistry, DeferredJobRegistry, FailedJobRegistry, FinishedJobRegistry, StartedJobRegistry
except (ImportError, ModuleNotFoundError):
    Job = None
    CanceledJobRegistry = None
    DeferredJobRegistry = None
    FailedJobRegistry = None
    FinishedJobRegistry = None
    StartedJobRegistry = None

try:
    from rq_scheduler import Scheduler
except ModuleNotFoundError:
    Scheduler = None


class ScheduledTaskRepository:
    def get_queue(self):
        queue = django_rq.get_queue('default')
        if queue.connection.ping() is not True:
            raise RuntimeError('Redis queue is unavailable.')
        return queue

    def get_scheduler(self):
        if Scheduler is None:
            raise RuntimeError('rq_scheduler is not installed. Install it to manage scheduled jobs.')
        queue = self.get_queue()
        return Scheduler(queue=queue, connection=queue.connection)

    def get_scheduler_jobs_with_times(self):
        return self.get_scheduler().get_jobs(with_times=True)

    def get_queue_jobs(self):
        if Job is None:
            raise RuntimeError('rq is not installed. Install it to inspect queue jobs.')

        queue = self.get_queue()
        job_ids = set(queue.job_ids)
        job_ids.update(StartedJobRegistry(queue=queue).get_job_ids())
        job_ids.update(FinishedJobRegistry(queue=queue).get_job_ids())
        job_ids.update(FailedJobRegistry(queue=queue).get_job_ids())
        job_ids.update(DeferredJobRegistry(queue=queue).get_job_ids())
        job_ids.update(CanceledJobRegistry(queue=queue).get_job_ids())
        return Job.fetch_many(sorted(job_ids)[:500], connection=queue.connection)

    def enqueue(self, func, kwargs):
        return self.get_queue().enqueue(func, kwargs=kwargs, result_ttl=86400, failure_ttl=604800)

    def enqueue_at(self, scheduled_time, func, kwargs):
        return self.get_scheduler().enqueue_at(scheduled_time, func, kwargs=kwargs, result_ttl=86400, failure_ttl=604800)

    def schedule(self, scheduled_time, func, kwargs, repeat):
        return self.get_scheduler().schedule(
            scheduled_time=scheduled_time,
            func=func,
            kwargs=kwargs,
            interval=int(repeat),
            result_ttl=max(86400, int(repeat) + 3600),
            failure_ttl=604800,
        )

    def cancel(self, job_id):
        if Job is None:
            raise RuntimeError('rq is not installed. Install it to cancel queue jobs.')

        queue = self.get_queue()
        job = self.job(job_id)
        if str(getattr(job.get_status(), 'value', job.get_status())) not in ('queued', 'scheduled', 'deferred'):
            raise ValidationError('Only queued, scheduled or deferred jobs can be cancelled.')
        scheduler = self.get_scheduler()
        if job_id in scheduler:
            scheduler.cancel(job_id)
        job.cancel()

    def job(self, job_id):
        queue = self.get_queue()
        if Job is None:
            raise RuntimeError('RQ is unavailable.')
        jobs = Job.fetch_many([job_id], connection=queue.connection)
        if not jobs or jobs[0] is None:
            raise NotFound('Job not found.')
        return jobs[0]

    def retry(self, job_id):
        queue = self.get_queue()
        job = self.job(job_id)
        if str(getattr(job.get_status(), 'value', job.get_status())) != 'failed':
            raise ValidationError('Only failed jobs can be retried.')
        return FailedJobRegistry(queue=queue).requeue(job)
