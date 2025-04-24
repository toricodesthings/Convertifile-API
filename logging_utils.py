from pathlib import Path
from loguru import logger
import sys

# Base directories configuration
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Default log configuration
DEFAULT_ROTATION = "10 MB"
DEFAULT_RETENTION = "1 day"
DEFAULT_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[request_id]: <12} | {module} | {message}"
CONSOLE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[request_id]: <12} | {module} | {message}"

# Clear default logger configuration
logger.remove()

# Configure the main application logger
def configure_main_logger():
    """Configure the main application logger with file and console handlers"""
    log_file = LOG_DIR / "app.log"
    
    # Add file handler
    logger.add(
        str(log_file),
        rotation=DEFAULT_ROTATION,
        retention=DEFAULT_RETENTION,
        format=DEFAULT_FORMAT
    )
    
    # Add console handler
    logger.add(
        sys.stdout,
        level="INFO",
        format=CONSOLE_FORMAT
    )
    
    return logger.bind(request_id="MAIN")

# Get a module-specific logger
def get_module_logger(module_name):
    """
    Get a logger configured for a specific module
    
    Args:
        module_name: Name of the module (e.g., 'imageconvert', 'documentconvert')
        
    Returns:
        A configured logger instance bound to the specified module
    """
    log_file = LOG_DIR / f"{module_name}.log"
    
    # Add a handler specific to this module
    logger.add(
        str(log_file),
        rotation=DEFAULT_ROTATION,
        retention=DEFAULT_RETENTION,
        format=DEFAULT_FORMAT,
        filter=lambda record: record["extra"].get("module") == module_name
    )
    
    # Return a logger bound to this module
    return logger.bind(module=module_name, request_id="-----")

# Function to get a request-specific logger
def get_request_logger(request_id):
    """Get a logger with the specified request ID"""
    return logger.bind(request_id=request_id)

# Initialize main logger
main_logger = configure_main_logger()
