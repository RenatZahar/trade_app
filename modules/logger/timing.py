import inspect
import logging
import time
from contextlib import contextmanager
from functools import wraps

from modules.logger.runtime_bootstrap import log_runtime_progress


logger = logging.getLogger("app")


def _format_timing_details(event, duration_sec=None, details=None) -> str:
    parts = [f"event={event}"]
    if duration_sec is not None:
        parts.append(f"duration_sec={round(duration_sec, 4)}")
    for key, value in (details or {}).items():
        parts.append(f"{key}={value}")
    return " ".join(parts)


def log_timing(event, duration_sec=None, **details):
    details_message = _format_timing_details(event, duration_sec, details)
    logger.info("PARSER_TIMING %s", details_message)
    log_runtime_progress(details_message)


@contextmanager
def timed_step(event, **details):
    start_time = time.perf_counter()
    try:
        yield details
    finally:
        log_timing(event, time.perf_counter() - start_time, **details)


def timed_log(event=None, **static_details):
    def decorator(func):
        event_name = event or f"{func.__module__}.{func.__name__}"

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                with timed_step(event_name, **static_details):
                    return await func(*args, **kwargs)

            return async_wrapper

        @wraps(func)
        def wrapper(*args, **kwargs):
            with timed_step(event_name, **static_details):
                return func(*args, **kwargs)

        return wrapper

    return decorator
