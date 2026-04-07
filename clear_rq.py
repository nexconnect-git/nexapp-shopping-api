import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

import django_rq
from rq_scheduler import Scheduler
queue = django_rq.get_queue('default')
scheduler = Scheduler(queue=queue, connection=queue.connection)
jobs = scheduler.get_jobs()
count = 0
for j in jobs:
    if 'check_assignment_timeout' in getattr(j, 'func_name', ''):
        scheduler.cancel(j.id)
        count += 1
print(f'Deleted {count} check_assignment_timeout jobs from scheduler')
