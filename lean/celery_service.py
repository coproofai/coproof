import os
from celery import Celery

celery = Celery(
    "lean_worker",
    broker=os.environ.get("REDIS_URL", "redis://redis:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://redis:6379/0"),
)

celery.conf.update(
    task_default_queue="lean_queue",
    task_routes={
        "tasks.*": {"queue": "lean_queue"},
    },
)

import tasks  # noqa: E402,F401
