import time
import logging
import sqlite3
from pathlib import Path

import sitecustomize  # noqa: F401

from modules.blockchain_parser import async_parser_functions as apf
from modules.blockchain_parser import main_parser
from modules.blockchain_parser.parser_runtime import start_btc_core_monitor_and_parser
from modules.bts_price_updater.runtime import update_btc_price_data
from modules.flask_module.flask_runtime import start_flask_app
from modules.sql_funcs.data_table_indexes import warn_required_data_table_indexes
from settings.paths import BLOCKS_SQL_DATA
from settings.parser import get_parser_runtime_profile, normalize_parser_runtime_profile
from settings.runtime import RuntimeConfigError, validate_runtime_dependencies
from settings.runtime_contracts import SCENARIO_RUNTIME_DEPENDENCIES


logger = logging.getLogger("app")


def normalize_collector_name(collector_name: str | None) -> str:
    return (collector_name or "legacy").strip().lower()


def warn_data_table_indexes_for_scenario(scenario_name: str) -> None:
    warn_required_data_table_indexes(BLOCKS_SQL_DATA, scenario_name)


def validate_main_pipeline_collector_requirements(collector_name: str | None) -> None:
    collector = normalize_collector_name(collector_name)
    if collector != "wallet-stats":
        return

    from modules.teach_and_update_models.wallet_stats_operations import (
        validate_wallet_stats_ready,
    )

    readiness = validate_wallet_stats_ready(BLOCKS_SQL_DATA)
    logger.info("wallet-stats collector preflight passed: %s", readiness)


def run_scenario_preflight(scenario_name: str):
    if scenario_name not in SCENARIO_RUNTIME_DEPENDENCIES:
        raise RuntimeConfigError(f"Unknown runtime scenario: {scenario_name}")

    dependency_names = SCENARIO_RUNTIME_DEPENDENCIES[scenario_name]
    try:
        validate_runtime_dependencies(dependency_names)
    except RuntimeConfigError:
        logger.exception("Runtime preflight failed for scenario %s", scenario_name)
        raise

    logger.info(
        "Runtime preflight passed for scenario %s: dependencies=%s",
        scenario_name,
        ", ".join(dependency_names) or "none",
    )
    return dependency_names


def validate_parser_background_resume_source(db_path) -> int:
    db_file = Path(db_path)
    if not db_file.exists():
        raise RuntimeConfigError(
            "Background parser requires an existing BLOCKS_SQL_DATA database: "
            f"{db_file}"
        )

    try:
        with sqlite3.connect(db_file) as db:
            last_block = db.execute("SELECT MAX(Block_height) FROM data_table;").fetchone()[0]
    except sqlite3.Error as exc:
        raise RuntimeConfigError(
            "Background parser could not read existing data_table from "
            f"BLOCKS_SQL_DATA: {db_file}"
        ) from exc

    if last_block is None:
        raise RuntimeConfigError(
            "Background parser refuses to start from an empty data_table; "
            "check BLOCKS_SQL_DATA before running a resume parser scenario."
        )
    logger.info("Background parser resume guard passed: last_block=%s", last_block)
    return int(last_block)


def prepare_training_data_and_train_new_model(collector_name: str = "legacy") -> None:
    from modules.finding_price_peaks.get_price_peaks_df import update_peaks
    from modules.teach_and_update_models.training_entrypoints import train_new_model_from_json

    run_scenario_preflight("main_pipeline")
    warn_data_table_indexes_for_scenario("main_pipeline")
    validate_main_pipeline_collector_requirements(collector_name)
    start_flask_app()
    update_btc_price_data()
    update_peaks()
    train_new_model_from_json(TEACHING_TEST=0, collector_name=collector_name)


def run_param_grid_scenario(test_fraction, seed=None) -> None:
    from modules.teach_and_update_models.training_entrypoints import run_param_grid

    run_scenario_preflight("param_grid")
    warn_data_table_indexes_for_scenario("param_grid")
    run_param_grid(TEACHING_TEST=test_fraction, seed=seed)


def run_parser_monitor_scenario(
    keep_alive: bool = True,
    tx_cache_lines: int | None = None,
    hash_cache_lines: int | None = None,
    parser_runtime_profile: str = "standard",
    bitcoin_core_profile: str = "standard",
    restart_bitcoin_core: bool = True,
) -> None:
    scenario_name = (
        "start_parser_background"
        if normalize_parser_runtime_profile(parser_runtime_profile) == "background"
        else "start_parser"
    )
    run_scenario_preflight(scenario_name)
    if scenario_name == "start_parser_background":
        validate_parser_background_resume_source(BLOCKS_SQL_DATA)
    parser_profile = get_parser_runtime_profile(parser_runtime_profile)
    cache_tx_lines = (
        tx_cache_lines
        if tx_cache_lines is not None
        else parser_profile["tx_cache_lines"]
    )
    cache_hash_lines = (
        hash_cache_lines
        if hash_cache_lines is not None
        else parser_profile["hash_cache_lines"]
    )
    apf.configure_cache_limits(
        tx_cache_lines=cache_tx_lines,
        hash_cache_lines=cache_hash_lines,
    )
    load_metadata = apf.configure_parser_load_limits(
        requests_quantity=parser_profile["requests_quantity"],
        async_rpc_batch_size=parser_profile["async_rpc_batch_size"],
        max_concurrent_block_tasks=parser_profile["max_concurrent_block_tasks"],
        max_save_tasks=parser_profile["max_save_tasks"],
    )
    group_metadata = main_parser.configure_parser_group_limits(
        quantity_of_blocks_in_iteration=parser_profile["quantity_of_blocks_in_iteration"],
        group_pause_seconds=parser_profile["group_pause_seconds"],
    )
    logger.info("Parser cache settings: %s", apf.get_cache_metadata())
    logger.info(
        "Parser runtime profile: profile=%s load=%s groups=%s",
        parser_runtime_profile,
        load_metadata,
        group_metadata,
    )
    warn_data_table_indexes_for_scenario(scenario_name)
    start_btc_core_monitor_and_parser(
        bitcoin_core_profile=bitcoin_core_profile,
        restart_bitcoin_core=restart_bitcoin_core,
    )
    if keep_alive:
        while True:
            time.sleep(1)


def run_downloaded_from_btc_data_scenario(
    blocks_count: int | None = None,
    seed: int | None = None,
    blocks: list[int] | None = None,
):
    from tests.integration_live.downloaded_from_btc_scenario import (
        run_downloaded_from_btc_data_test_scenario,
    )

    run_scenario_preflight("integration_live.downloaded_from_btc_data")
    warn_data_table_indexes_for_scenario("integration_live.downloaded_from_btc_data")
    return run_downloaded_from_btc_data_test_scenario(
        blocks_count=blocks_count,
        seed=seed,
        requested_blocks=blocks,
    )


