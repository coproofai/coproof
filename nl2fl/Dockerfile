FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY celery_service.py tasks.py nl2fl_service.py ./

CMD ["celery", "-A", "celery_service.celery", "worker", "-Q", "nl2fl_queue", "--loglevel=info"]
