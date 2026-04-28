from argparse import Namespace

from modules.logger import run_tracker


def test_get_arg_collects_only_truthy_values():
    args = Namespace(start_parser=True, test="param_grid", service=None)

    result = run_tracker.get_arg(args)

    assert result == "start_parser, True, test, param_grid"


def test_run_tracker_tracks_stage_and_finish(monkeypatch):
    monkeypatch.setattr(run_tracker, "get_init_number", lambda: 42)
    tracker = run_tracker.RunTracker(Namespace(start_parser=False, test="flask", service=None))

    stage_data = tracker.start_stage("bootstrap")
    finished_stage = tracker.finish_stage(status="success", details="ok")
    run_data = tracker.finish_run("success")

    assert tracker.id == 42
    assert stage_data["stage"] == "bootstrap"
    assert finished_stage["status"] == "success"
    assert finished_stage["details"] == "ok"
    assert run_data["status"] == "success"
    assert run_data["error"] is None
    assert run_data["stages"][0]["stage"] == "bootstrap"
