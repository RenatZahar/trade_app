# logger.py

import logging
import sys
from logging.handlers import RotatingFileHandler
from settings.paths import BASE_DIR

LOGS_DIR = BASE_DIR / "logs"
FILE_LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
CONSOLE_LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"

def setup_logging(module_name, log_level=logging.INFO):
    LOGS_DIR.mkdir(exist_ok=True)

    logger = logging.getLogger(module_name)
    if logger.handlers:
        return logger

    logger.setLevel(log_level)
    logger.propagate = False

    file_handler = RotatingFileHandler(
        LOGS_DIR / f"{module_name}.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(FILE_LOG_FORMAT))

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(CONSOLE_LOG_FORMAT))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
