import os
from app import create_app
from app.extensions import celery

print(f"--- CELERY WORKER STARTUP ---")
print(f"Raw DATABASE_URL env: {os.environ.get('DATABASE_URL')}")

app = create_app()
app.app_context().push()

print(f"Final SQLALCHEMY_DATABASE_URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
print(f"-----------------------------")