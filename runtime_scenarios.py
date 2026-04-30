import time

from modules.blockchain_parser.parser_runtime import start_btc_core_monitor_and_parser
from modules.bts_price_updater.runtime import update_btc_price_data
from modules.flask_module.flask_runtime import start_flask_app
from modules.sql_funcs.data_table_indexes import warn_required_data_table_indexes
from settings.paths import BLOCKS_SQL_DATA


def warn_data_table_indexes_for_scenario(scenario_name: str) -> None:
    warn_required_data_table_indexes(BLOCKS_SQL_DATA, scenario_name)


def prepare_training_data_and_train_new_model() -> None:
    from modules.finding_price_peaks.get_price_peaks_df import update_peaks
    from modules.teach_and_update_models.training_entrypoints import train_new_model_from_json

    warn_data_table_indexes_for_scenario("main_pipeline")
    start_flask_app()
    update_btc_price_data()
    update_peaks()
    train_new_model_from_json(TEACHING_TEST=0)


def run_param_grid_scenario(test_fraction, seed=None) -> None:
    from modules.teach_and_update_models.training_entrypoints import run_param_grid

    warn_data_table_indexes_for_scenario("param_grid")
    run_param_grid(TEACHING_TEST=test_fraction, seed=seed)


def run_parser_monitor_scenario(keep_alive: bool = True) -> None:
    warn_data_table_indexes_for_scenario("start_parser")
    start_btc_core_monitor_and_parser()
    if keep_alive:
        while True:
            time.sleep(1)


def run_downloaded_from_btc_data_scenario(blocks_count: int, seed: int | None = None):
    from tests.integration_live.downloaded_from_btc_scenario import (
        run_downloaded_from_btc_data_test_scenario,
    )

    warn_data_table_indexes_for_scenario("integration_live.downloaded_from_btc_data")
    return run_downloaded_from_btc_data_test_scenario(
        blocks_count=blocks_count,
        seed=seed,
    )


