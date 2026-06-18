import django_rq

try:
    from rq.job import Job
    from rq.registry import DeferredJobRegistry, FailedJobRegistry, FinishedJobRegistry, StartedJobRegistry
except (ImportError, ModuleNotFoundError):
    Job = None
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
        return django_rq.get_queue('default')

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
        return Job.fetch_many(list(job_ids), connection=queue.connection)

    def enqueue(self, func, kwargs):
        return self.get_queue().enqueue(func, **kwargs)

    def enqueue_at(self, scheduled_time, func, kwargs):
        return self.get_scheduler().enqueue_at(scheduled_time, func, **kwargs)

    def schedule(self, scheduled_time, func, kwargs, repeat):
        return self.get_scheduler().schedule(
            scheduled_time=scheduled_time,
            func=func,
            kwargs=kwargs,
            interval=int(repeat),
        )

    def cancel(self, job_id):
        if Job is None:
            raise RuntimeError('rq is not installed. Install it to cancel queue jobs.')

        queue = self.get_queue()
        try:
            job = Job.fetch(job_id, connection=queue.connection)
            job.delete()
        except Exception:
            pass

        scheduler = self.get_scheduler()
        if job_id in scheduler:
            scheduler.cancel(job_id)
