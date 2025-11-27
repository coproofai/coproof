# Use an official Python runtime as a parent image
FROM python:3.11-slim-buster

# Set environment variables
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing pyc files to disc
# PYTHONUNBUFFERED: Prevents Python from buffering stdout and stderr
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /usr/src/app

# Install system dependencies
# git: Required for GitPython
# libpq-dev: Required for psycopg2
# gcc: Required for compiling some python deps
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    libpq-dev \
    && apt-get clean

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create storage directory for Git Engine (Ephemeral)
RUN mkdir -p /tmp/coproof-storage

# Expose port
EXPOSE 8000

# Default command (Production)
# Uses Gunicorn with Gevent workers for async performance
CMD ["gunicorn", "-k", "gevent", "-w", "1", "-b", "0.0.0.0:8000", "wsgi:app"]