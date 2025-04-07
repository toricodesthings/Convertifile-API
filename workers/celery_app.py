#Celery Main App and Loader

from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env file

celery = Celery(
    "convertifile",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_BACKEND_URL", "redis://localhost:6379/0"),
)
