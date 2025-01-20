# scraper_project/utils/logging_config.py
import logging
from typing import Optional


def configure_logging(level: Optional[str] = None) -> None:
    """
    Configure logging globally for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Set default level to INFO if none provided
    log_level = getattr(logging, level.upper()) if level else logging.INFO

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Suppress unnecessary selenium logging
    logging.getLogger('selenium').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    # Suppress other verbose loggers
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
