To run this locally:
- Start Redis (for Cache/Celery).
- Start Postgres.
- Run flask db init, migrate, upgrade.
- Run celery -A app.tasks worker --loglevel=info.
- Run flask run.