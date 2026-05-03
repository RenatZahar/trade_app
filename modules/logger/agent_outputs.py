import json
from datetime import datetime
from pathlib import Path

from settings.paths import BASE_DIR


LOGS_DIR = BASE_DIR / "logs"
AGENT_RUNS_DIR = LOGS_DIR / "agent_runs"
SCHEMA_VERSION = 1


def get_agent_run_dir(run_id) -> Path:
    return AGENT_RUNS_DIR / str(run_id)


def get_agent_artifact_paths(run_id) -> dict:
    run_dir = get_agent_run_dir(run_id)
    return {
        "log": str(LOGS_DIR / f"{run_id}.log"),
        "manifest": str(run_dir / "manifest.json"),
        "events": str(run_dir / "events.jsonl"),
        "summary": str(run_dir / "summary.json"),
    }


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2, default=str)
        file.write("\n")
    temp_path.replace(path)


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False, default=str))
        file.write("\n")


def _base_event(tracker, event: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "event": event,
        "run_id": tracker.id,
        "status": tracker.status,
        "timestamp": _now_iso(),
    }


def write_manifest(tracker) -> None:
    run_data = tracker.get_run_data()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now_iso(),
        "run_id": run_data["run_id"],
        "start_arg": run_data["start_arg"],
        "args": run_data["args"],
        "started_at": run_data["started_at"],
        "started_at_ts": run_data["started_at_ts"],
        "status": run_data["status"],
        "metadata": run_data["metadata"],
        "artifacts": get_agent_artifact_paths(run_data["run_id"]),
    }
    _write_json_atomic(get_agent_run_dir(run_data["run_id"]) / "manifest.json", payload)


def append_run_event(tracker, event: str, details=None) -> None:
    payload = _base_event(tracker, event)
    payload.update(
        {
            "start_arg": tracker.start_arg,
            "started_at": tracker.started_at,
            "finished_at": tracker.finished_at,
            "duration_sec": tracker.duration_sec,
            "duration_human": tracker.duration_human,
            "error": tracker.error,
        }
    )
    if details is not None:
        payload["details"] = details
    _append_jsonl(get_agent_run_dir(tracker.id) / "events.jsonl", payload)


def append_metadata_event(tracker) -> None:
    payload = _base_event(tracker, "run_metadata")
    payload["metadata"] = tracker.get_run_data().get("metadata", {})
    _append_jsonl(get_agent_run_dir(tracker.id) / "events.jsonl", payload)


def append_stage_started(tracker, stage_data: dict) -> None:
    payload = _base_event(tracker, "stage_started")
    payload.update(stage_data)
    _append_jsonl(get_agent_run_dir(tracker.id) / "events.jsonl", payload)


def append_stage_finished(tracker, stage_data: dict) -> None:
    payload = _base_event(tracker, "stage_finished")
    payload.update(stage_data)
    _append_jsonl(get_agent_run_dir(tracker.id) / "events.jsonl", payload)


def append_stage_progress(tracker, details) -> None:
    payload = _base_event(tracker, "stage_progress")
    payload.update(
        {
            "stage": tracker.current_stage,
            "started_at": tracker.current_stage_started_at,
            "details": details,
        }
    )
    _append_jsonl(get_agent_run_dir(tracker.id) / "events.jsonl", payload)


def write_summary(tracker) -> None:
    run_data = tracker.get_run_data()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now_iso(),
        **run_data,
        "artifacts": get_agent_artifact_paths(run_data["run_id"]),
    }
    _write_json_atomic(get_agent_run_dir(run_data["run_id"]) / "summary.json", payload)
