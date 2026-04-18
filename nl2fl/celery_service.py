import os
from celery import Celery

queue_name = os.environ.get('CELERY_NL2FL_QUEUE', 'nl2fl_queue')

celery = Celery(
    'nl2fl_worker',
    broker=os.environ.get('REDIS_URL', 'redis://redis:6379/0'),
    backend=os.environ.get('REDIS_URL', 'redis://redis:6379/0'),
)

celery.conf.update(
    task_default_queue=queue_name,
    task_routes={
        'tasks.*': {'queue': queue_name},
    },
)

import tasks  # noqa: E402,F401
