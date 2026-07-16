import logging
import sys
from datetime import datetime
from typing import Optional


class CustomFormatter(logging.Formatter):
    """Custom formatter with [TIMESTAMP] [LEVEL] message format"""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level = record.levelname
        message = record.getMessage()
        return f"[{timestamp}] [{level}] {message}"


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Setup and return a logger instance with custom formatting.

    Args:
        name: Logger name (typically __name__)
        level: Logging level (DEBUG, INFO, ERROR, etc.)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    if logger.handlers:
        logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(CustomFormatter())

    logger.addHandler(console_handler)

    return logger


# Global logger instance for API
api_logger = setup_logger("api", logging.INFO)
