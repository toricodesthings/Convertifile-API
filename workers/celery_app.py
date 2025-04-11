# Celery Main App and Configuration Loader
from celery import Celery
from dotenv import load_dotenv
from celery.schedules import crontab

# Load environment variables first (helpful for local development)
load_dotenv()

# Create the Celery app with standard configuration
celery = Celery("convertifile")

# Load configuration from the dedicated config module
celery.config_from_object('workers.celeryconfig')

# CLeanup task for temporary files on schedule
celery.conf.beat_schedule = {
    'cleanup-every-30-minutes': {
        'task': 'cleanup_temp_files',
        'schedule': 30 * 60,  # 30 minutes in seconds
        # Alternative: use crontab for more control
        # 'schedule': crontab(minute='0,30'),  # Run at :00 and :30 of every hour
    },
}

# Log the connection URL (helpful for debugging)
print(f"Celery configured with broker: {celery.conf.broker_url}")