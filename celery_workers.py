# filepath: c:\Users\Shep\Desktop\API Apps\convertifile-api\celery_workers.py
# celery_worker.py

from workers.celery_app import celery

# Export the Celery app instance for use in other modules
app = celery

# Celery will automatically discover tasks in the specified modules
import workers.tasks