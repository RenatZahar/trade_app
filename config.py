# config.py

import os
from pathlib import Path
import sys
import colorama
import sqlite3



def _max_sql_vars():
    # #коммент: читаем compile-options у in-memory БД; файл базы не трогаем
    try:
        with sqlite3.connect(":memory:") as conn:
            for (opt,) in conn.execute("PRAGMA compile_options;"):
                if opt.startswith("MAX_VARIABLE_NUMBER="):
                    return int(opt.split("=", 1)[1])
    except Exception:
        pass
    return 999 




MIN_TXS_PER_WALLET = int(os.getenv('MIN_TXS_PER_WALLET', 5))
TOTAL_AMOUNT_MORE_THAN_BTC = float(os.getenv('TOTAL_AMOUNT_MORE_THAN_BTC', 0.1))
TXS_PER_WALLET_MORE_THAN = int(os.getenv('TXS_PER_WALLET_MORE_THAN', 1)) #Указывает количество транзакций, при котором кошелек считается "активным" и они не перемещаются в few_tx_wallets

TRAINED_MODELS_DIR =  BASE_DIR / Path(os.getenv('TRAINED_MODELS_DIR', 'data\\models\\trained_models'))
REDIS_PROCESS_NAME = "redis-server.exe"  # Имя процесса Redis для Windows
# REDIS_EXECUTABLE_PATH = os.getenv('REDIS_EXECUTABLE_PATH', 'C:\\Redis\\redis-server.exe')  # Путь к redis-server.exe
REDIS_EXECUTABLE_PATH  = os.getenv('REDIS_EXECUTABLE_PATH', 'C:\\Program Files\\Redis\\redis-server.exe')

RAW_BTC_PRICE_DIR_FILE = BASE_DIR / Path(os.getenv('RAW_BTC_PRICE_DIR_FILE', 'data/bitcoin_price/raw_btc_price/BTCUSDT.csv.gz'))
# TXS_PARQUET_DIR = BASE_DIR / Path(os.getenv('TXS_DIR', 'data/blocks_parquet_data'))
# CLEARED_PRICES_DIR = BASE_DIR / Path(os.getenv('CLEARED_PRICES_DIR', 'data/bitcoin_price/cleared_btc_price'))



NEW_MODELS_PATH  = BASE_DIR / Path(os.getenv('NEW_MODELS_PATH', 'data/models/new_models'))
# BLOCKS_SQL_DATA = BASE_DIR / Path(os.getenv('BLOCKS_SQL_DATA', 'data/blocks_sql_data/blocks_sql_data_db.db'))

BLOCK_HEIGHT_BLOCK_TIME_MAP_DIR_FILE = BASE_DIR /Path(os.getenv('BLOCK_HEIGHT_BLOCK_TIME_MAP_DIR_FILE', 'data/block_height_block_time_map/map.parquet'))

DASK_TEMP_DIR = Path(os.getenv('DASK_TEMP_DIR', 'C:/dask-temp'))
APP_TEMP_DIR = BASE_DIR / Path(os.getenv('APP_TEMP_DIR', 'data/temp'))
PARAM_GRID_DIR = BASE_DIR / Path(os.getenv('PARAM_GRID_DIR', 'data/param_grids'))
NEW_PARAM_GRID_DIR = PARAM_GRID_DIR / Path(os.getenv('NEW_PARAM_GRID_DIR', 'new_grids'))
PARAM_GRID_RESULTS = PARAM_GRID_DIR / Path(os.getenv('PARAM_GRID_RESULTS', 'param_grid_results'))

BLOCKS_SQL_DATA = Path(os.getenv('BLOCKS_SQL_DATA', 'data/blocks_sql_data/blocks_sql_data_db.db'))
SQL_LIMIT_BATCH_SIZE =  min(int(_max_sql_vars()*0.9), 5000) # возможная точка для оптимизации (900 для SQL_IN_LIST_MAX — для размера IN (?,…,?) и SQL_EXECUTEMANY_BATCH — для «строк на коммит» в executemany (можно держать больше, чем IN))
