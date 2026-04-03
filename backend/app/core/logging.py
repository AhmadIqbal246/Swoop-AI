import os
import sys
import logging
from app.core.config import get_settings

settings = get_settings()

def setup_logging():
    """
    Sets up a centralized logging configuration for the entire application.
    Routes logs to both Console and File.
    """
    # 1. Create Logs Directory if it doesn't exist
    log_file = settings.LOG_FILE_PATH
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 2. Configure Root Logger
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # 3. Create a Custom Logger Instance
    logger = logging.getLogger("SwoopAI")
    
    # Silence third-party noise if needed
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    
    logger.info("Structured Logging Initialized Successfully.")
    return logger

# Create a singleton logger for the app
app_logger = setup_logging()
