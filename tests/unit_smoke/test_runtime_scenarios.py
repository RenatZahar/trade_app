import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

import runtime_scenarios as scenarios
from settings.runtime import RuntimeConfigError, required_env_names_for


def test_import_runtime_scenarios_does_not_change_cwd_or_load_lazy_scenario_modules():
    project_root = Path(__file__).resolve().parents[2]
    code = """
import json
import os
import sys

before = os.getcwd()
import runtime_scenarios
after = os.getcwd()

print(json.dumps({
    "cwd_unchanged": before == after,
    "training_entrypoints_loaded": "modules.teach_and_update_models.training_entrypoints" in sys.modules,
    "training_orchestrator_loaded": "modules.teach_and_update_models.orchestrator" in sys.modules,
    "integration_live_helper_loaded": "tests.integration_live.downloaded_from_btc_scenario" in sys.modules,
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)

    assert payload == {
        "cwd_unchanged": True,
        "training_entrypoints_loaded": False,
        "training_orchestrator_loaded": False,
        "integration_live_helper_loaded": False,
    }


def test_prepare_training_data_and_train_new_model_orders_pipeline_steps(monkeypatch):
    calls = []
    peaks_module = types.ModuleType("modules.finding_price_peaks.get_price_peaks_df")
    peaks_module.update_peaks = lambda: calls.append("update_peaks")
    training_module = types.ModuleType("modules.teach_and_update_models.training_entrypoints")
    training_module.train_new_model_from_json = (
        lambda TEACHING_TEST, seed=None: calls.append(("teach_and_update_models", TEACHING_TEST, seed))
    )
    monkeypatch.setitem(sys.modules, "modules.finding_price_peaks.get_price_peaks_df", peaks_module)
    monkeypatch.setitem(
        sys.modules,
        "modules.teach_and_update_models.training_entrypoints",
        training_module,
    )
    monkeypatch.setattr(
        scenarios,
        "warn_data_table_indexes_for_scenario",
        lambda scenario_name: calls.append(("warn_indexes", scenario_name)),
    )
    monkeypatch.setattr(
        scenarios,
        "run_scenario_preflight",
        lambda scenario_name: calls.append(("preflight", scenario_name)),
    )
    monkeypatch.setattr(scenarios, "start_flask_app", lambda: calls.append("start_flask_app"))
    monkeypatch.setattr(scenarios, "update_btc_price_data", lambda: calls.append("update_btc_price_data"))

    scenarios.prepare_training_data_and_train_new_model()

    assert calls == [
        ("preflight", "main_pipeline"),
        ("warn_indexes", "main_pipeline"),
        "start_flask_app",
        "update_btc_price_data",
        "update_peaks",
        ("teach_and_update_models", 0, None),
    ]


def test_run_param_grid_scenario_orders_steps(monkeypatch):
    calls = []
    training_module = types.ModuleType("modules.teach_and_update_models.training_entrypoints")
    training_module.run_param_grid = (
        lambda TEACHING_TEST, seed=None: calls.append(("run_param_grid", TEACHING_TEST, seed))
    )
    monkeypatch.setitem(
        sys.modules,
        "modules.teach_and_update_models.training_entrypoints",
        training_module,
    )
    monkeypatch.setattr(
        scenarios,
        "warn_data_table_indexes_for_scenario",
        lambda scenario_name: calls.append(("warn_indexes", scenario_name)),
    )
    monkeypatch.setattr(
        scenarios,
        "run_scenario_preflight",
        lambda scenario_name: calls.append(("preflight", scenario_name)),
    )

    scenarios.run_param_grid_scenario(test_fraction=0.25, seed=13)

    assert calls == [
        ("preflight", "param_grid"),
        ("warn_indexes", "param_grid"),
        ("run_param_grid", 0.25, 13),
    ]


def test_run_parser_monitor_scenario_orders_steps(monkeypatch):
    calls = []
    monkeypatch.setattr(
        scenarios,
        "warn_data_table_indexes_for_scenario",
        lambda scenario_name: calls.append(("warn_indexes", scenario_name)),
    )
    monkeypatch.setattr(
        scenarios,
        "run_scenario_preflight",
        lambda scenario_name: calls.append(("preflight", scenario_name)),
    )
    monkeypatch.setattr(
        scenarios,
        "start_btc_core_monitor_and_parser",
        lambda: calls.append("start_btc_core_monitor_and_parser"),
    )

    scenarios.run_parser_monitor_scenario(keep_alive=False)

    assert calls == [
        ("preflight", "start_parser"),
        ("warn_indexes", "start_parser"),
        "start_btc_core_monitor_and_parser",
    ]


def test_run_downloaded_from_btc_data_scenario_orders_steps(monkeypatch):
    calls = []
    helper_module = types.ModuleType("tests.integration_live.downloaded_from_btc_scenario")
    helper_module.run_downloaded_from_btc_data_test_scenario = (
        lambda blocks_count, seed=None: calls.append(("run_downloaded_btc", blocks_count, seed))
        or {"status": "finished"}
    )
    monkeypatch.setitem(
        sys.modules,
        "tests.integration_live.downloaded_from_btc_scenario",
        helper_module,
    )
    monkeypatch.setattr(
        scenarios,
        "warn_data_table_indexes_for_scenario",
        lambda scenario_name: calls.append(("warn_indexes", scenario_name)),
    )
    monkeypatch.setattr(
        scenarios,
        "run_scenario_preflight",
        lambda scenario_name: calls.append(("preflight", scenario_name)),
    )

    result = scenarios.run_downloaded_from_btc_data_scenario(blocks_count=3, seed=21)

    assert result == {"status": "finished"}
    assert calls == [
        ("preflight", "integration_live.downloaded_from_btc_data"),
        ("warn_indexes", "integration_live.downloaded_from_btc_data"),
        ("run_downloaded_btc", 3, 21),
    ]


def test_scenario_preflight_matrix_declares_external_service_dependencies():
    assert scenarios.SCENARIO_RUNTIME_DEPENDENCIES["start_parser"] == (
        "blocks_sql_data",
        "redis",
        "bitcoin_core",
    )
    assert scenarios.SCENARIO_RUNTIME_DEPENDENCIES[
        "integration_live.downloaded_from_btc_data"
    ] == ("blocks_sql_data", "bitcoin_rpc")


def test_run_scenario_preflight_reports_missing_external_service_env(monkeypatch):
    for env_name in required_env_names_for(["redis", "bitcoin_core"]):
        monkeypatch.delenv(env_name, raising=False)

    with pytest.raises(RuntimeConfigError, match="Missing required environment variables"):
        scenarios.run_scenario_preflight("start_parser")
