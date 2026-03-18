FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_CONFIG=production

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y \
    git \
    gcc \
    libpq-dev \
    && apt-get clean

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /tmp/coproof-storage

EXPOSE 8000

CMD ["gunicorn", "-k", "gevent", "-w", "1", "-b", "0.0.0.0:8000", "run_prod:app"]