"""Structured logging configuration."""

import logging
import sys
from app.core.config import settings

def setup_logging() -> logging.Logger:
    """Configure structured logger for the application."""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    # Keep our own debug output but silence chatty libraries (they log every network packet).
    for noisy in ("httpx", "httpcore", "asyncio", "hpack"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logger = logging.getLogger("fixmycampus")
    logger.setLevel(log_level)
    return logger

logger = setup_logging()
