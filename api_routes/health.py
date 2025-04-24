from fastapi import APIRouter
import platform
import time
from datetime import datetime
import sys
import os

# Track when the service started
START_TIME = time.time()

router = APIRouter()

# Function to check if running in Docker
def is_in_docker():
    # Method 1: Check for .dockerenv file
    if os.path.exists('/.dockerenv'):
        return True
    
    # Method 2: Check for DOCKER_CONTAINER environment variable
    return os.environ.get('DOCKER_CONTAINER', '').lower() == 'true'

def is_development():
    # If running in Docker, consider it production unless explicitly set to development
    if is_in_docker() or os.environ.get("ENVIRONMENT", "").lower() != "development":
        return False
    return True

@router.get("/")
@router.get("")
def health_check():
    uptime_seconds = time.time() - START_TIME
    
    health_data = {
        "status": "normal",
        "timestamp": datetime.now().isoformat(),
        "uptime": {
            "seconds": round(uptime_seconds, 2),
            "formatted": f"{int(uptime_seconds // 86400)}d {int((uptime_seconds % 86400) // 3600)}h {int((uptime_seconds % 3600) // 60)}m {int(uptime_seconds % 60)}s"
        },
        "system_info": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "environment": os.environ.get("ENVIRONMENT", "production"),
            "in_docker": is_in_docker()
        },
    }
    
    return health_data
