import os

# Use explicit environment variables with fallbacks
broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')
result_backend = os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')

broker_url_set = True
result_backend_set = True

task_serializer = 'json'
accept_content = ['json']
result_serializer = 'json'
timezone = 'UTC'
enable_utc = True

# Set Redis visibility timeout
broker_transport_options = {
    'visibility_timeout': 3600,  # 1 hour
}

worker_hijack_root_logger = False
worker_redirect_stdouts = False

broker_connection_retry_on_startup = True