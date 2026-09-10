"""
Logger Utility
Centralised logging for the InsureClear pipeline.
Logs to console and optionally to a file in logs/ directory.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

_logger = None


def get_logger(name: str = "insureclear", log_to_file: bool = True) -> logging.Logger:
    """
    Get or create the InsureClear logger.
    First call creates the logger; subsequent calls return the same instance.
    """
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Console handler — INFO level, clean format
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console_fmt = logging.Formatter(
        "%(message)s"
    )
    console.setFormatter(console_fmt)
    logger.addHandler(console)

    # File handler — DEBUG level, full format
    if log_to_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOGS_DIR / f"pipeline_{timestamp}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_fmt)
        logger.addHandler(file_handler)

    _logger = logger
    return logger
