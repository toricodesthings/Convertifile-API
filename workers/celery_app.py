"""Celery Main App and Configuration Loader"""

from celery import Celery
from dotenv import load_dotenv

# Load environment variables first (helpful for local development)
load_dotenv()

# Create the Celery app with standard configuration
celery = Celery("convertifile")

# Load configuration from the dedicated config module
celery.config_from_object('workers.celeryconfig')

# Log the connection URL (helpful for debugging)
print(f"Celery configured with broker: {celery.conf.broker_url}")