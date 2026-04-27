# logger.py

import logging
import queue
import sys
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from settings.paths import BASE_DIR

LOGS_DIR = BASE_DIR / "logs"
FILE_LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] %(message)s"
CONSOLE_LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] %(message)s"
APP_LOGGER_NAME = "app"

_LOG_QUEUE = None
_LOG_LISTENER = None

def setup_logging(id_, log_level=logging.INFO):
    global _LOG_QUEUE, _LOG_LISTENER

    LOGS_DIR.mkdir(exist_ok=True)

    logger = logging.getLogger(APP_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(log_level)
    logger.propagate = False

    file_handler = RotatingFileHandler(
        LOGS_DIR / f"{id_}.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(FILE_LOG_FORMAT))

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(CONSOLE_LOG_FORMAT))

    _LOG_QUEUE = queue.Queue(-1)
    queue_handler = QueueHandler(_LOG_QUEUE)
    queue_handler.setLevel(log_level)

    _LOG_LISTENER = QueueListener(
        _LOG_QUEUE,
        file_handler,
        console_handler,
        respect_handler_level=True    
        )
    _LOG_LISTENER.start()

    logger.addHandler(queue_handler)

    return logger

def stop_logging():
    global _LOG_LISTENER, _LOG_QUEUE

    if _LOG_LISTENER is not None:
        _LOG_LISTENER.stop()
        _LOG_LISTENER = None
    _LOG_QUEUE = None

def log_tracker_run_event(tracker, event, details=None, level=logging.INFO):
    logger = logging.getLogger(APP_LOGGER_NAME)
    tracker_data = tracker.get_run_data()

    message = (
        f"_TRACKER_INFO event={event} "
        f"run_id={tracker_data['run_id']} "
        f"status={tracker_data['status']} "
        f"start_arg={tracker_data['start_arg']} "
        f"started_at={tracker_data['started_at']} "
        f"finished_at={tracker_data['finished_at']} "
        f"duration_sec={tracker_data['duration_sec']} "
        f"duration_human={tracker_data['duration_human']} "
        f"error={tracker_data['error']}"
    )

    if details is not None:
        message += f" details={details}"

    logger.log(level, message)

def log_tracker_stage_started(tracker, stage_data):
    logger = logging.getLogger(APP_LOGGER_NAME)
    logger.info(
        f"_TRACKER_INFO event=stage_started "
        f"run_id={tracker.id} "
        f"stage={stage_data['stage']} "
        f"status={stage_data['status']} "
        f"started_at={stage_data['started_at']}"
    )

def log_tracker_stage_finished(tracker, stage_data):
    logger = logging.getLogger(APP_LOGGER_NAME)
    logger.info(
        f"_TRACKER_INFO event=stage_finished "
        f"run_id={tracker.id} "
        f"stage={stage_data['stage']} "
        f"status={stage_data['status']} "
        f"started_at={stage_data['started_at']} "
        f"duration_sec={stage_data['duration_sec']} "
        f"duration_human={stage_data['duration_human']} "
        f"details={stage_data['details']}"
    )


def log_tracker_stage_progress(tracker, details):
    logger = logging.getLogger(APP_LOGGER_NAME)
    logger.info(
        f"_TRACKER_INFO event=stage_progress "
        f"run_id={tracker.id} "
        f"stage={tracker.current_stage} "
        f"status=running "
        f"started_at={tracker.current_stage_started_at} "
        f"details={details}"
    )

