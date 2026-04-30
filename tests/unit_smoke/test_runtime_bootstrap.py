from argparse import Namespace

import pytest

from modules.logger import run_tracker
from modules.logger import runtime_bootstrap as rb


def test_tracked_stage_uses_callable_name_by_default(monkeypatch):
    monkeypatch.setattr(run_tracker, "get_init_number", lambda: 101)
    monkeypatch.setattr(rb.app_logger_module, "log_tracker_stage_started", lambda tracker, stage: None)
    monkeypatch.setattr(rb.app_logger_module, "log_tracker_stage_finished", lambda tracker, stage: None)
    tracker = run_tracker.RunTracker(Namespace(command="service"))

    def sample_stage():
        return None

    with rb.tracked_stage(tracker, sample_stage, success_details="ok"):
        sample_stage()

    assert tracker.stages[0]["stage"] == "sample_stage"
    assert tracker.stages[0]["status"] == "success"
    assert tracker.stages[0]["details"] == "ok"


def test_tracked_stage_accepts_explicit_stage_name(monkeypatch):
    monkeypatch.setattr(run_tracker, "get_init_number", lambda: 102)
    monkeypatch.setattr(rb.app_logger_module, "log_tracker_stage_started", lambda tracker, stage: None)
    monkeypatch.setattr(rb.app_logger_module, "log_tracker_stage_finished", lambda tracker, stage: None)
    tracker = run_tracker.RunTracker(Namespace(command="service"))

    with rb.tracked_stage(tracker, "service.custom", success_details="ok"):
        pass

    assert tracker.stages[0]["stage"] == "service.custom"


def test_tracked_stage_records_error_and_reraises(monkeypatch):
    monkeypatch.setattr(run_tracker, "get_init_number", lambda: 103)
    monkeypatch.setattr(rb.app_logger_module, "log_tracker_stage_started", lambda tracker, stage: None)
    monkeypatch.setattr(rb.app_logger_module, "log_tracker_stage_finished", lambda tracker, stage: None)
    tracker = run_tracker.RunTracker(Namespace(command="service"))

    with pytest.raises(RuntimeError):
        with rb.tracked_stage(tracker, "service.failure"):
            raise RuntimeError("boom")

    assert tracker.stages[0]["stage"] == "service.failure"
    assert tracker.stages[0]["status"] == "error"
    assert tracker.stages[0]["details"] == "boom"


def test_finish_runtime_success_finishes_run_and_logs_event(monkeypatch):
    run_events = []
    monkeypatch.setattr(run_tracker, "get_init_number", lambda: 104)
    monkeypatch.setattr(
        rb.app_logger_module,
        "log_tracker_run_event",
        lambda tracker, event, level=None: run_events.append((event, level)),
    )
    tracker = run_tracker.RunTracker(Namespace(command="service"))

    rb.finish_runtime_success(tracker)

    assert tracker.status == "success"
    assert tracker.finished_at is not None
    assert tracker.duration_sec is not None
    assert run_events == [("run_finished", None)]


def test_update_runtime_metadata_merges_and_logs_metadata(monkeypatch):
    metadata_events = []
    monkeypatch.setattr(run_tracker, "get_init_number", lambda: 105)
    monkeypatch.setattr(
        rb.app_logger_module,
        "log_tracker_metadata",
        lambda tracker: metadata_events.append(dict(tracker.metadata)),
    )
    tracker = run_tracker.RunTracker(Namespace(command="service"), metadata={"seed": 13})

    metadata = rb.update_runtime_metadata(tracker, model_params={"alpha": 0.1})

    assert metadata["seed"] == 13
    assert metadata["model_params"] == {"alpha": 0.1}
    assert tracker.metadata["model_params"] == {"alpha": 0.1}
    assert metadata_events == [{"seed": 13, "model_params": {"alpha": 0.1}}]


def test_finish_runtime_interrupted_finishes_active_stage_and_run(monkeypatch):
    stage_events = []
    run_events = []
    monkeypatch.setattr(run_tracker, "get_init_number", lambda: 106)
    monkeypatch.setattr(rb.app_logger_module, "log_tracker_stage_finished", lambda tracker, stage: stage_events.append(stage))
    monkeypatch.setattr(
        rb.app_logger_module,
        "log_tracker_run_event",
        lambda tracker, event, level=None: run_events.append((event, level)),
    )
    tracker = run_tracker.RunTracker(Namespace(command="service"))
    tracker.start_stage("service.active")

    rb.finish_runtime_interrupted(tracker, KeyboardInterrupt("stop"))

    assert tracker.status == "interrupted"
    assert tracker.error == "stop"
    assert tracker.current_stage is None
    assert stage_events[0]["stage"] == "service.active"
    assert stage_events[0]["status"] == "interrupted"
    assert run_events == [("run_finished", None)]


def test_finish_runtime_error_finishes_active_stage_and_logs_error(monkeypatch):
    stage_events = []
    run_events = []
    monkeypatch.setattr(run_tracker, "get_init_number", lambda: 107)
    monkeypatch.setattr(rb.app_logger_module, "log_tracker_stage_finished", lambda tracker, stage: stage_events.append(stage))
    monkeypatch.setattr(
        rb.app_logger_module,
        "log_tracker_run_event",
        lambda tracker, event, level=None: run_events.append((event, level)),
    )
    tracker = run_tracker.RunTracker(Namespace(command="service"))
    tracker.start_stage("service.active")

    rb.finish_runtime_error(tracker, RuntimeError("boom"))

    assert tracker.status == "error"
    assert tracker.error == "boom"
    assert tracker.current_stage is None
    assert stage_events[0]["stage"] == "service.active"
    assert stage_events[0]["status"] == "error"
    assert run_events == [("run_finished", rb.logging.ERROR)]


def test_finish_runtime_error_without_active_stage_only_finishes_run(monkeypatch):
    stage_events = []
    run_events = []
    monkeypatch.setattr(run_tracker, "get_init_number", lambda: 108)
    monkeypatch.setattr(rb.app_logger_module, "log_tracker_stage_finished", lambda tracker, stage: stage_events.append(stage))
    monkeypatch.setattr(
        rb.app_logger_module,
        "log_tracker_run_event",
        lambda tracker, event, level=None: run_events.append((event, level)),
    )
    tracker = run_tracker.RunTracker(Namespace(command="service"))

    rb.finish_runtime_error(tracker, RuntimeError("boom"))

    assert tracker.status == "error"
    assert stage_events == []
    assert run_events == [("run_finished", rb.logging.ERROR)]
