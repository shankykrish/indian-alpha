import sys
import os
from typing import Optional
from loguru import logger
from indian_alpha.config import HISTORY_DIR

def setup_logging(log_file: Optional[str] = None) -> None:
    """Configures Loguru logger for console output and a persistent file log."""
    if log_file is None:
        log_file = os.path.join(HISTORY_DIR, "app.log")
        
    # Ensure logs directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    # Clear default logger settings
    logger.remove()

    # Add stdout handler with rich coloring
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True
    )

    # Add persistent file handler
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="zip"
    )
    
    logger.info("Observability Logging Initialized Successfully.")
