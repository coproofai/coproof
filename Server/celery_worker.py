from app import create_app
from app.extensions import celery

# We need an app context to initialize Celery configuration
app = create_app()
app.app_context().push()

# The 'celery' object is now configured and ready for the worker process
# TODO: Phase 6 - Ensure tasks are imported here or in app/__init__ so Celery detects them