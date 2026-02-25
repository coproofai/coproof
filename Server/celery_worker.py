import os
from app import create_app
from app.extensions import celery

# DEBUG: Print the raw environment variable before App creation
print(f"--- CELERY WORKER STARTUP ---")
print(f"Raw DATABASE_URL env: {os.environ.get('DATABASE_URL')}")

app = create_app()
app.app_context().push()

# DEBUG: Print the final SQLAlchemy URI configuration
print(f"Final SQLALCHEMY_DATABASE_URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
print(f"-----------------------------")

# The 'celery' object is now configured and ready for the worker process
# TODO: Phase 6 - Ensure tasks are imported here or in app/__init__ so Celery detects them