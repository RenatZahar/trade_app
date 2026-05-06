import logging
from contextlib import contextmanager

import modules.logger.logger as app_logger_module
from modules.logger import agent_outputs
from modules.logger.experiment_metadata import build_experiment_metadata
from modules.logger.run_tracker import RunTracker, get_current_run_tracker


def start_runtime_logging(args):
    tracker = RunTracker(args, metadata=build_experiment_metadata(args))
    app_logger_module.setup_logging(tracker.id)
    agent_outputs.write_manifest(tracker)
    logger = logging.getLogger("app")
    logger.warning(f"Старт main.py, прогон № {tracker.id}")
    app_logger_module.log_tracker_run_event(tracker, "run_started")
    app_logger_module.log_tracker_metadata(tracker)
    return tracker, logger


def update_runtime_metadata(tracker, **metadata_updates):
    metadata = dict(tracker.metadata)
    metadata.update({key: value for key, value in metadata_updates.items() if value is not None})
    tracker.set_metadata(metadata)
    app_logger_module.log_tracker_metadata(tracker)
    return metadata


def log_runtime_progress(details):
    try:
        tracker = get_current_run_tracker()
    except RuntimeError:
        return

    if tracker.current_stage is not None:
        app_logger_module.log_tracker_stage_progress(tracker, details)


def _resolve_stage_name(stage):
    if isinstance(stage, str):
        return stage
    if callable(stage):
        return stage.__name__
    raise TypeError("stage must be a string stage name or a callable")


@contextmanager
def tracked_stage(tracker, stage, success_details=None):
    stage_name = _resolve_stage_name(stage)
    stage_data = tracker.start_stage(stage_name)
    app_logger_module.log_tracker_stage_started(tracker, stage_data)

    try:
        yield
    except Exception as e:
        stage_data = tracker.finish_stage("error", details=str(e))
        app_logger_module.log_tracker_stage_finished(tracker, stage_data)
        raise
    else:
        if callable(success_details):
            success_details = success_details()
        stage_data = tracker.finish_stage("success", details=success_details)
        app_logger_module.log_tracker_stage_finished(tracker, stage_data)


def finish_runtime_success(tracker):
    tracker.finish_run("success")
    app_logger_module.log_tracker_run_event(tracker, "run_finished")


def _finish_current_stage_if_needed(tracker, status, details=None):
    if tracker.current_stage is None:
        return None

    stage_data = tracker.finish_stage(status, details=details)
    app_logger_module.log_tracker_stage_finished(tracker, stage_data)
    return stage_data


def finish_runtime_interrupted(tracker, error):
    _finish_current_stage_if_needed(tracker, "interrupted", details=str(error))
    tracker.finish_run("interrupted", error)
    app_logger_module.log_tracker_run_event(tracker, "run_finished")


def finish_runtime_error(tracker, error):
    _finish_current_stage_if_needed(tracker, "error", details=str(error))
    tracker.finish_run("error", error)
    app_logger_module.log_tracker_run_event(tracker, "run_finished", level=logging.ERROR)
