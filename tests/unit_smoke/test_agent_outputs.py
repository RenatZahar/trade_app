import json
from argparse import Namespace
from pathlib import Path

from modules.logger import agent_outputs
from modules.logger import logger as app_logger_module
from modules.logger import run_tracker
from modules.logger import runtime_bootstrap


def _read_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _read_jsonl(path):
    with open(path, "r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def test_agent_outputs_write_manifest_events_and_summary(tmp_path, monkeypatch):
    logs_dir = tmp_path / "logs"
    monkeypatch.setattr(agent_outputs, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(agent_outputs, "AGENT_RUNS_DIR", logs_dir / "agent_runs")
    monkeypatch.setattr(run_tracker, "get_init_number", lambda: 501)
    tracker = run_tracker.RunTracker(
        Namespace(command="param-grid", test_fraction=0.1, seed=42),
        metadata={"seed": 42, "commit_hash": "abc123"},
    )

    agent_outputs.write_manifest(tracker)
    app_logger_module.log_tracker_run_event(tracker, "run_started")
    stage_data = tracker.start_stage("features.correlation_data")
    app_logger_module.log_tracker_stage_started(tracker, stage_data)
    finished_stage = tracker.finish_stage("success", details={"iteration": 1})
    app_logger_module.log_tracker_stage_finished(tracker, finished_stage)
    tracker.finish_run("success")
    app_logger_module.log_tracker_run_event(tracker, "run_finished")

    run_dir = logs_dir / "agent_runs" / "501"
    manifest = _read_json(run_dir / "manifest.json")
    events = _read_jsonl(run_dir / "events.jsonl")
    summary = _read_json(run_dir / "summary.json")

    assert manifest["run_id"] == 501
    assert manifest["args"]["command"] == "param-grid"
    assert manifest["metadata"]["seed"] == 42
    assert [event["event"] for event in events] == [
        "run_started",
        "stage_started",
        "stage_finished",
        "run_finished",
    ]
    assert events[2]["stage"] == "features.correlation_data"
    assert events[2]["details"] == {"iteration": 1}
    assert summary["status"] == "success"
    assert summary["stages"][0]["stage"] == "features.correlation_data"
    assert Path(summary["artifacts"]["events"]).parts[-3:] == (
        "agent_runs",
        "501",
        "events.jsonl",
    )


def test_runtime_bootstrap_writes_agent_artifacts(tmp_path, monkeypatch):
    logs_dir = tmp_path / "logs"
    monkeypatch.setattr(agent_outputs, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(agent_outputs, "AGENT_RUNS_DIR", logs_dir / "agent_runs")
    monkeypatch.setattr(app_logger_module, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(run_tracker, "get_init_number", lambda: 502)

    tracker, _logger = runtime_bootstrap.start_runtime_logging(
        Namespace(command="test", data_test="downloaded-from-btc-data", seed=7)
    )
    with runtime_bootstrap.tracked_stage(tracker, "integration_live.sample", success_details="ok"):
        pass
    runtime_bootstrap.finish_runtime_success(tracker)
    app_logger_module.stop_logging()

    run_dir = logs_dir / "agent_runs" / "502"
    manifest = _read_json(run_dir / "manifest.json")
    events = _read_jsonl(run_dir / "events.jsonl")
    summary = _read_json(run_dir / "summary.json")

    assert manifest["run_id"] == 502
    assert events[0]["event"] == "run_started"
    assert any(event["event"] == "run_metadata" for event in events)
    assert any(event["event"] == "stage_finished" for event in events)
    assert events[-1]["event"] == "run_finished"
    assert summary["status"] == "success"
    assert summary["stages"][0]["details"] == "ok"
