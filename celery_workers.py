"""Celery worker initialization and task discovery."""

from workers.celery_app import celery

# Export the Celery app instance for use in other modules
app = celery

# Celery will automatically discover tasks in the specified modules
import workers.tasks

print(f"Celery worker configured with broker: {app.conf.broker_url}")