# converge_of_elsticnet.py

import os
import time
import pandas as pd
import dask.dataframe as dd
from .tests_utils_funcs import save_parquet
from config import BLOCKS_SQL_DATA, APP_TEMP_DIR
from modules.logger.logger import setup_logging
from modules.teach_and_update_models.data_operations import get_data_for_teach_with_dask, clean_data
from modules.dask_client_init.get_dask_client import get_dask_client, close_dask_client


logger = setup_logging(__name__)
script_dir = os.path.dirname(os.path.abspath(__file__))
module_name_for_temp_dir = __name__.replace('.', '_')
dir_for_temp_files_of_module = os.path.join(APP_TEMP_DIR, module_name_for_temp_dir)
os.makedirs(dir_for_temp_files_of_module, exist_ok=True)
os.chdir(script_dir)

# функция перезаписи данных для теста - если что то сохраняется, предыдущие файл по директории должны удаляться (учесть папку или паркет файл?)
    # если файл - сохранять с *.parquet, нет - без
# в тесте надо импортиротвать все функции повторяя рабочий процесс, но при этом регулировать точки входа - указывать скрипту откуда начинаем работу
# как вообще понять почему регрессионная модель не сходится?
# попробовать прописать классы моделей- 
    # дерево решений, лес решений, пни решений, градиент бустинг модел чтобы это не значило, sklearn.linear_model.Ridge/RidgeCV
 

def converge_of_elasticnet(tmps=None, correlation_type=None):
    logger.info("\033[34mStart converge_of_elasticnet\033[0m")
    dask_client = get_dask_client()
    # check_for_temp_data_available() дописать функцию по копированию дата? скорее всего не понадобится

    all_txs_of_wallets_ddf_dir = os.path.join(dir_for_temp_files_of_module, 'txs_of_chunk_with_intervals')
    all_wallets_corelation_ddf_dir = os.path.join(dir_for_temp_files_of_module, 'correlation_wallets_df')
    all_txs_of_wallets_ddf = dd.read_parquet(all_txs_of_wallets_ddf_dir)
    all_wallets_corelation_ddf = dd.read_parquet(all_wallets_corelation_ddf_dir)

    if not correlation_type:
        correlation_type = 'basic'
    if not tmps: 
        tmps = {'model_relevance_start_tmsp': 1733311411, 'model_relevance_end_tmsp': 1738495411, 'profit_test_start_tmsp': 1728127410, 'profit_test_end_tmsp': 1733311410, 'teaching_start_tmsp': 1697023409, 'teaching_end_tmsp': 1728127409, 'cmlt_start_tmsp': 1695813808, 'cmlt_end_tmsp': 1697023408}
    
    cor_data_in_iteration_to_teach_df, cor_data_in_iteration_to_profit_test_df = get_data_for_teach_with_dask(tmps, all_txs_of_wallets_ddf, all_wallets_corelation_ddf, correlation_type, converge_test = 1, dir_for_save_test_data = dir_for_temp_files_of_module)
    
    logger.info("Closing dask client")
    close_dask_client(dask_client)
    cor_data_in_iteration_to_teach_df.reset_index(inplace=True)
    cor_data_in_iteration_to_profit_test_df.reset_index(inplace=True)
    cor_data_in_iteration_to_teach_df = clean_data(cor_data_in_iteration_to_teach_df)
    cor_data_in_iteration_to_profit_test_df = clean_data(cor_data_in_iteration_to_profit_test_df)


if __name__ == '__main__':
    converge_of_elasticnet()
