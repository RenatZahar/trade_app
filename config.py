# config.py

import os
from pathlib import Path
from dotenv import load_dotenv
import sys
import redis

load_dotenv()

import logging

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# в конфиге - только пути, не константы
RAW_BTC_PRICE_DIR_FILE = BASE_DIR / Path(os.getenv('RAW_BTC_PRICE_DIR_FILE', 'data/bitcoin_price/raw_btc_price/BTCUSDT.csv.gz'))
TXS_PARQUET_DIR = BASE_DIR / Path(os.getenv('TXS_DIR', 'data/blocks_parquet_data'))
CLEARED_PRICES_DIR = BASE_DIR / Path(os.getenv('CLEARED_PRICES_DIR', 'data/bitcoin_price/cleared_btc_price'))
CLEARED_PRICES_DIR_FILE = CLEARED_PRICES_DIR / os.listdir(CLEARED_PRICES_DIR)[1]
BTC_PRICES_WITH_INTERVALS_FILE = BASE_DIR / Path(os.getenv('BTC_PRICES_WITH_INTERVALS_FILE', 'data/bitcoin_price/cleared_btc_price'))


BLOCKS_SQL_DATA = Path(os.getenv('BLOCKS_SQL_DATA', 'data/blocks_sql_data/blocks_sql_data_db.db'))
REDIS_EXECUTABLE_PATH  = os.getenv('REDIS_EXECUTABLE_PATH', 'C:\\Program Files\\Redis\\redis-server.exe')

# BLOCKS_SQL_DATA = BASE_DIR / Path(os.getenv('BLOCKS_SQL_DATA', 'data/blocks_sql_data/blocks_sql_data_db.db'))


def setup_logging(module_name):

    if not os.path.exists(os.path.join(BASE_DIR, 'logs')):
        os.makedirs(os.path.join(BASE_DIR, 'logs'))

    # Define the log file path
    log_file = os.path.join(BASE_DIR, 'logs', f'{module_name}.log')

    # Create a logger for the module
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.INFO)

    # Define the logging format
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s')

    # Create a file handler that logs to the module-specific file
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    # Create a stream handler that logs to the console
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger


