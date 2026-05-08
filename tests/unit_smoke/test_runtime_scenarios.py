import json
import sqlite3
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
        lambda TEACHING_TEST, seed=None, collector_name="legacy": calls.append(
            ("teach_and_update_models", TEACHING_TEST, seed, collector_name)
        )
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
        "validate_main_pipeline_collector_requirements",
        lambda collector_name: calls.append(("collector_preflight", collector_name)),
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
        ("collector_preflight", "legacy"),
        "start_flask_app",
        "update_btc_price_data",
        "update_peaks",
        ("teach_and_update_models", 0, None, "legacy"),
    ]


def test_prepare_training_data_and_train_new_model_passes_collector(monkeypatch):
    calls = []
    peaks_module = types.ModuleType("modules.finding_price_peaks.get_price_peaks_df")
    peaks_module.update_peaks = lambda: calls.append("update_peaks")
    training_module = types.ModuleType("modules.teach_and_update_models.training_entrypoints")
    training_module.train_new_model_from_json = (
        lambda TEACHING_TEST, seed=None, collector_name="legacy": calls.append(
            ("teach_and_update_models", TEACHING_TEST, seed, collector_name)
        )
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
        "validate_main_pipeline_collector_requirements",
        lambda collector_name: calls.append(("collector_preflight", collector_name)),
    )
    monkeypatch.setattr(
        scenarios,
        "run_scenario_preflight",
        lambda scenario_name: calls.append(("preflight", scenario_name)),
    )
    monkeypatch.setattr(scenarios, "start_flask_app", lambda: calls.append("start_flask_app"))
    monkeypatch.setattr(scenarios, "update_btc_price_data", lambda: calls.append("update_btc_price_data"))

    scenarios.prepare_training_data_and_train_new_model(collector_name="wallet-stats")

    assert calls == [
        ("preflight", "main_pipeline"),
        ("warn_indexes", "main_pipeline"),
        ("collector_preflight", "wallet-stats"),
        "start_flask_app",
        "update_btc_price_data",
        "update_peaks",
        ("teach_and_update_models", 0, None, "wallet-stats"),
    ]


def test_validate_main_pipeline_collector_requirements_checks_wallet_stats(monkeypatch):
    calls = []
    wallet_stats_module = types.ModuleType(
        "modules.teach_and_update_models.wallet_stats_operations"
    )
    wallet_stats_module.validate_wallet_stats_ready = (
        lambda db_path: calls.append(db_path) or {"status": "ready"}
    )
    monkeypatch.setitem(
        sys.modules,
        "modules.teach_and_update_models.wallet_stats_operations",
        wallet_stats_module,
    )

    scenarios.validate_main_pipeline_collector_requirements("legacy")
    assert calls == []

    scenarios.validate_main_pipeline_collector_requirements("wallet-stats")
    assert calls == [scenarios.BLOCKS_SQL_DATA]


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


def test_run_wallet_stats_rebuild_scenario_orders_steps(monkeypatch):
    calls = []
    wallet_stats_module = types.ModuleType(
        "modules.teach_and_update_models.wallet_stats_operations"
    )
    wallet_stats_module.rebuild_wallet_stats = (
        lambda db_path, target_until_block=None, block_chunk_size=10000: calls.append(
            (
                "rebuild_wallet_stats",
                db_path,
                target_until_block,
                block_chunk_size,
            )
        )
        or {"stats_until_block": target_until_block}
    )
    monkeypatch.setitem(
        sys.modules,
        "modules.teach_and_update_models.wallet_stats_operations",
        wallet_stats_module,
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

    result = scenarios.run_wallet_stats_rebuild_scenario(
        target_until_block=883457,
        block_chunk_size=10000,
    )

    assert calls == [
        ("preflight", "wallet_stats_rebuild"),
        ("warn_indexes", "wallet_stats_rebuild"),
        (
            "rebuild_wallet_stats",
            scenarios.BLOCKS_SQL_DATA,
            883457,
            10000,
        ),
    ]
    assert result == {"stats_until_block": 883457}


def test_run_parser_monitor_scenario_orders_steps(monkeypatch):
    calls = []
    cache_settings = []
    load_settings = []
    group_settings = []
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
        lambda bitcoin_core_profile="standard", restart_bitcoin_core=True: calls.append(
            (
                "start_btc_core_monitor_and_parser",
                bitcoin_core_profile,
                restart_bitcoin_core,
            )
        ),
    )
    monkeypatch.setattr(
        scenarios.apf,
        "configure_cache_limits",
        lambda tx_cache_lines=None, hash_cache_lines=None: cache_settings.append(
            (tx_cache_lines, hash_cache_lines)
        ),
    )
    monkeypatch.setattr(
        scenarios.apf,
        "configure_parser_load_limits",
        lambda requests_quantity=None,
        max_save_tasks=None,
        async_rpc_batch_size=None,
        max_concurrent_block_tasks=None: load_settings.append(
            (
                requests_quantity,
                max_save_tasks,
                async_rpc_batch_size,
                max_concurrent_block_tasks,
            )
        )
        or {
            "requests_quantity": requests_quantity,
            "max_save_tasks": max_save_tasks,
            "async_rpc_batch_size": async_rpc_batch_size,
            "max_concurrent_block_tasks": max_concurrent_block_tasks,
        },
    )
    monkeypatch.setattr(
        scenarios.apf,
        "get_cache_metadata",
        lambda: {"max_lines_in_tx_cache": 0, "max_lines_in_hash_cache": 0},
    )
    monkeypatch.setattr(
        scenarios.main_parser,
        "configure_parser_group_limits",
        lambda quantity_of_blocks_in_iteration=None, group_pause_seconds=None: group_settings.append(
            (quantity_of_blocks_in_iteration, group_pause_seconds)
        )
        or {
            "quantity_of_blocks_in_iteration": quantity_of_blocks_in_iteration,
            "group_pause_seconds": group_pause_seconds,
        },
    )

    scenarios.run_parser_monitor_scenario(
        keep_alive=False,
        tx_cache_lines=0,
        hash_cache_lines=0,
    )

    assert calls == [
        ("preflight", "start_parser"),
        ("warn_indexes", "start_parser"),
        ("start_btc_core_monitor_and_parser", "standard", True),
    ]
    assert cache_settings == [(0, 0)]
    assert load_settings == [(800, 1, 2000, 4)]
    assert group_settings == [(40, 0)]


def test_run_parser_monitor_scenario_background_profile_orders_steps(monkeypatch):
    calls = []
    cache_settings = []
    load_settings = []
    group_settings = []
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
        "validate_parser_background_resume_source",
        lambda db_path: calls.append(("resume_guard", db_path)) or 877672,
    )
    monkeypatch.setattr(
        scenarios,
        "start_btc_core_monitor_and_parser",
        lambda bitcoin_core_profile="standard", restart_bitcoin_core=False: calls.append(
            (
                "start_btc_core_monitor_and_parser",
                bitcoin_core_profile,
                restart_bitcoin_core,
            )
        ),
    )
    monkeypatch.setattr(
        scenarios.apf,
        "configure_cache_limits",
        lambda tx_cache_lines=None, hash_cache_lines=None: cache_settings.append(
            (tx_cache_lines, hash_cache_lines)
        ),
    )
    monkeypatch.setattr(
        scenarios.apf,
        "configure_parser_load_limits",
        lambda requests_quantity=None,
        max_save_tasks=None,
        async_rpc_batch_size=None,
        max_concurrent_block_tasks=None: load_settings.append(
            (
                requests_quantity,
                max_save_tasks,
                async_rpc_batch_size,
                max_concurrent_block_tasks,
            )
        )
        or {
            "requests_quantity": requests_quantity,
            "max_save_tasks": max_save_tasks,
            "async_rpc_batch_size": async_rpc_batch_size,
            "max_concurrent_block_tasks": max_concurrent_block_tasks,
        },
    )
    monkeypatch.setattr(
        scenarios.apf,
        "get_cache_metadata",
        lambda: {"max_lines_in_tx_cache": 20000, "max_lines_in_hash_cache": 0},
    )
    monkeypatch.setattr(
        scenarios.main_parser,
        "configure_parser_group_limits",
        lambda quantity_of_blocks_in_iteration=None, group_pause_seconds=None: group_settings.append(
            (quantity_of_blocks_in_iteration, group_pause_seconds)
        )
        or {
            "quantity_of_blocks_in_iteration": quantity_of_blocks_in_iteration,
            "group_pause_seconds": group_pause_seconds,
        },
    )

    scenarios.run_parser_monitor_scenario(
        keep_alive=False,
        parser_runtime_profile="background",
        bitcoin_core_profile="background",
        restart_bitcoin_core=True,
    )

    assert calls == [
        ("preflight", "start_parser_background"),
        ("resume_guard", scenarios.BLOCKS_SQL_DATA),
        ("warn_indexes", "start_parser_background"),
        ("start_btc_core_monitor_and_parser", "background", True),
    ]
    assert cache_settings == [(20000, 0)]
    assert load_settings == [(100, 1, 300, 1)]
    assert group_settings == [(4, 5)]


def test_validate_parser_background_resume_source_rejects_missing_db(tmp_path):
    missing_db = tmp_path / "missing.db"

    with pytest.raises(RuntimeConfigError, match="existing BLOCKS_SQL_DATA"):
        scenarios.validate_parser_background_resume_source(missing_db)


def test_validate_parser_background_resume_source_rejects_empty_data_table(tmp_path):
    db_path = tmp_path / "blocks.db"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE data_table (Block_height INTEGER);")
        db.commit()

    with pytest.raises(RuntimeConfigError, match="empty data_table"):
        scenarios.validate_parser_background_resume_source(db_path)


def test_validate_parser_background_resume_source_returns_last_block(tmp_path):
    db_path = tmp_path / "blocks.db"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE data_table (Block_height INTEGER);")
        db.execute("INSERT INTO data_table (Block_height) VALUES (877672);")
        db.commit()

    assert scenarios.validate_parser_background_resume_source(db_path) == 877672


def test_run_downloaded_from_btc_data_scenario_orders_steps(monkeypatch):
    calls = []
    helper_module = types.ModuleType("tests.integration_live.downloaded_from_btc_scenario")
    helper_module.run_downloaded_from_btc_data_test_scenario = (
        lambda blocks_count=None, seed=None, requested_blocks=None: calls.append(
            ("run_downloaded_btc", blocks_count, seed, requested_blocks)
        )
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

    result = scenarios.run_downloaded_from_btc_data_scenario(
        blocks_count=3,
        seed=21,
        blocks=[873754, 873755],
    )

    assert result == {"status": "finished"}
    assert calls == [
        ("preflight", "integration_live.downloaded_from_btc_data"),
        ("warn_indexes", "integration_live.downloaded_from_btc_data"),
        ("run_downloaded_btc", 3, 21, [873754, 873755]),
    ]


def test_scenario_preflight_matrix_declares_external_service_dependencies():
    assert scenarios.SCENARIO_RUNTIME_DEPENDENCIES["start_parser"] == (
        "blocks_sql_data",
        "redis",
        "bitcoin_core",
    )
    assert scenarios.SCENARIO_RUNTIME_DEPENDENCIES["start_parser_background"] == (
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
