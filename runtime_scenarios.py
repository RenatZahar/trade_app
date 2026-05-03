import time
import logging

from modules.blockchain_parser import async_parser_functions as apf
from modules.blockchain_parser.parser_runtime import start_btc_core_monitor_and_parser
from modules.bts_price_updater.runtime import update_btc_price_data
from modules.flask_module.flask_runtime import start_flask_app
from modules.sql_funcs.data_table_indexes import warn_required_data_table_indexes
from settings.paths import BLOCKS_SQL_DATA
from settings.runtime import RuntimeConfigError, validate_runtime_dependencies
from settings.runtime_contracts import SCENARIO_RUNTIME_DEPENDENCIES


logger = logging.getLogger("app")


def warn_data_table_indexes_for_scenario(scenario_name: str) -> None:
    warn_required_data_table_indexes(BLOCKS_SQL_DATA, scenario_name)


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


def prepare_training_data_and_train_new_model() -> None:
    from modules.finding_price_peaks.get_price_peaks_df import update_peaks
    from modules.teach_and_update_models.training_entrypoints import train_new_model_from_json

    run_scenario_preflight("main_pipeline")
    warn_data_table_indexes_for_scenario("main_pipeline")
    start_flask_app()
    update_btc_price_data()
    update_peaks()
    train_new_model_from_json(TEACHING_TEST=0)


def run_param_grid_scenario(test_fraction, seed=None) -> None:
    from modules.teach_and_update_models.training_entrypoints import run_param_grid

    run_scenario_preflight("param_grid")
    warn_data_table_indexes_for_scenario("param_grid")
    run_param_grid(TEACHING_TEST=test_fraction, seed=seed)


def run_parser_monitor_scenario(
    keep_alive: bool = True,
    tx_cache_lines: int | None = None,
    hash_cache_lines: int | None = None,
) -> None:
    run_scenario_preflight("start_parser")
    apf.configure_cache_limits(
        tx_cache_lines=tx_cache_lines,
        hash_cache_lines=hash_cache_lines,
    )
    logger.info("Parser cache settings: %s", apf.get_cache_metadata())
    warn_data_table_indexes_for_scenario("start_parser")
    start_btc_core_monitor_and_parser()
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


