FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY computation_service.py celery_service.py tasks.py ./

CMD ["celery", "-A", "celery_service.celery", "worker", "-Q", "cluster_computation_queue", "--loglevel=info"]
