import logging
import time
from pathlib import Path
from datetime import datetime
import config

def ensure_directories():
    """Ensure all required application directories exist."""
    config.DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    config.ASSETS_DIR.mkdir(parents=True, exist_ok=True)

def setup_logging():
    """Configure application-wide logging."""
    ensure_directories()
    
    logger = logging.getLogger("FIM_Tool")
    logger.setLevel(logging.DEBUG)
    
    # Avoid duplicate handlers if setup is called multiple times
    if logger.handlers:
        return logger

    # File handler
    file_handler = logging.FileHandler(config.LOG_PATH, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def get_logger():
    """Get the standard logger instance."""
    return logging.getLogger("FIM_Tool")

def format_size(bytes_size: int) -> str:
    """Format file size into human-readable representation."""
    if bytes_size is None:
        return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}" if unit != 'B' else f"{bytes_size} B"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"

def format_timestamp(timestamp: float) -> str:
    """Format Unix timestamp to human-readable string."""
    if timestamp is None:
        return "N/A"
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "N/A"
