# converge_of_elsticnet.py
"""
Debug-сценарий для старого модельного flow.

Смысл: проверить, что ранее сохраненные parquet-артефакты можно прогнать через
get_data_for_teach_with_dask/clean_data и получить непустые DataFrame для
обучения и profit-test. Это не обязательный pytest-сценарий.
"""

import os
import sys
from pathlib import Path

import dask.dataframe as dd

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from modules.teach_and_update_models.data_operations import clean_data, get_data_for_teach_with_dask
from modules.dask_client_init.get_dask_client import close_dask_client, get_dask_client
from settings.paths import APP_TEMP_DIR

import logging

logger = logging.getLogger("app")
module_name_for_temp_dir = "modules_tests_converge_of_elasticnet"
dir_for_temp_files_of_module = os.path.join(APP_TEMP_DIR, module_name_for_temp_dir)
os.makedirs(dir_for_temp_files_of_module, exist_ok=True)

# TODO(iteration_12): решить, нужен ли этот сценарий как часть artifact-based
# сравнения current pipeline и legacy notebook pipeline. Если нет, удалить.


def converge_of_elasticnet(tmps=None, correlation_type=None):
    logger.info("\033[34mStart converge_of_elasticnet\033[0m")
    dask_client = None

    all_txs_of_wallets_ddf_dir = os.path.join(dir_for_temp_files_of_module, "txs_of_chunk_with_intervals")
    all_wallets_corelation_ddf_dir = os.path.join(dir_for_temp_files_of_module, "correlation_wallets_df")
    if not os.path.exists(all_txs_of_wallets_ddf_dir):
        raise FileNotFoundError(f"Не найдена директория с транзакциями для converge test: {all_txs_of_wallets_ddf_dir}")
    if not os.path.exists(all_wallets_corelation_ddf_dir):
        raise FileNotFoundError(f"Не найдена директория с корреляциями для converge test: {all_wallets_corelation_ddf_dir}")

    if not correlation_type:
        correlation_type = "basic"
    if not tmps:
        tmps = {
            "model_relevance_start_tmsp": 1733311411,
            "model_relevance_end_tmsp": 1738495411,
            "profit_test_start_tmsp": 1728127410,
            "profit_test_end_tmsp": 1733311410,
            "teaching_start_tmsp": 1697023409,
            "teaching_end_tmsp": 1728127409,
            "cmlt_start_tmsp": 1695813808,
            "cmlt_end_tmsp": 1697023408,
        }

    try:
        dask_client = get_dask_client()
        all_txs_of_wallets_ddf = dd.read_parquet(all_txs_of_wallets_ddf_dir)
        all_wallets_corelation_ddf = dd.read_parquet(all_wallets_corelation_ddf_dir)

        cor_data_in_iteration_to_teach_df, cor_data_in_iteration_to_profit_test_df = get_data_for_teach_with_dask(
            tmps,
            all_txs_of_wallets_ddf,
            all_wallets_corelation_ddf,
            correlation_type,
            converge_test=1,
            dir_for_save_test_data=dir_for_temp_files_of_module,
        )

        cor_data_in_iteration_to_teach_df.reset_index(inplace=True)
        cor_data_in_iteration_to_profit_test_df.reset_index(inplace=True)
        cor_data_in_iteration_to_teach_df = clean_data(cor_data_in_iteration_to_teach_df)
        cor_data_in_iteration_to_profit_test_df = clean_data(cor_data_in_iteration_to_profit_test_df)

        if cor_data_in_iteration_to_teach_df.empty:
            raise RuntimeError("Converge test produced empty teaching dataframe.")
        if cor_data_in_iteration_to_profit_test_df.empty:
            raise RuntimeError("Converge test produced empty profit-test dataframe.")

        logger.info("Converge ElasticNet test data prepared successfully.")
    finally:
        if dask_client:
            logger.info("Closing dask client")
            close_dask_client(dask_client)


if __name__ == "__main__":
    converge_of_elasticnet()
