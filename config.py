# config.py

import os
from pathlib import Path
from dotenv import load_dotenv
import sys

load_dotenv()

import logging

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

rpc_user=os.getenv('RPC_USER')
rpc_password=os.getenv('RPC_PASSWORD')
rpc_host=os.getenv('RPC_HOST')
rpc_port=os.getenv('RPC_PORT')

LINE_TIME_DURATION_MIN = int(os.getenv('LINE_TIME_DURATION_MIN', 10))
TRAINED_MODELS_DIR =  BASE_DIR / Path(os.getenv('TRAINED_MODELS_DIR', 'data\\models\\trained_models'))
REDIS_PROCESS_NAME = "redis-server.exe"  # Имя процесса Redis для Windows
# REDIS_EXECUTABLE_PATH = os.getenv('REDIS_EXECUTABLE_PATH', 'C:\\Redis\\redis-server.exe')  # Путь к redis-server.exe
REDIS_EXECUTABLE_PATH  = os.getenv('REDIS_EXECUTABLE_PATH', 'C:\\Program Files\\Redis\\redis-server.exe')

RAW_BTC_PRICE_DIR_FILE = BASE_DIR / Path(os.getenv('RAW_BTC_PRICE_DIR_FILE', 'data/bitcoin_price/raw_btc_price/BTCUSDT.csv.gz'))
TXS_PARQUET_DIR = BASE_DIR / Path(os.getenv('TXS_DIR', 'data/blocks_parquet_data'))
CLEARED_PRICES_DIR = BASE_DIR / Path(os.getenv('CLEARED_PRICES_DIR', 'data/bitcoin_price/cleared_btc_price'))
CLEARED_PRICES_DIR_FILE = CLEARED_PRICES_DIR / os.listdir(CLEARED_PRICES_DIR)[1]
BTC_PRICES_WITH_PEAKS_AND_INTERVALS_FILE = BASE_DIR / Path(os.getenv('BTC_PRICES_WITH_PEAKS_AND_INTERVALS_FILE', 'data\bitcoin_price\btc_price_df_with_intervals\btc_price_df_with_intervals.parquet'))

BLOCKS_SQL_DATA = Path(os.getenv('BLOCKS_SQL_DATA', 'data/blocks_sql_data/blocks_sql_data_db.db'))

NEW_MODELS_PATH  = BASE_DIR / Path(os.getenv('NEW_MODELS_PATH', 'data/models/new_models'))
# BLOCKS_SQL_DATA = BASE_DIR / Path(os.getenv('BLOCKS_SQL_DATA', 'data/blocks_sql_data/blocks_sql_data_db.db'))



def setup_logging(module_name):

    if not os.path.exists(os.path.join(BASE_DIR, 'logs')):
        os.makedirs(os.path.join(BASE_DIR, 'logs'))

    # Определяем путь к файлу логов
    log_file = os.path.join(BASE_DIR, 'logs', f'{module_name}.log')

    # Создаем пользовательский класс логгера
    class ExcInfoLogger(logging.Logger):
        def error(self, msg, *args, **kwargs):
            # Проверяем, обрабатывается ли исключение
            if 'exc_info' not in kwargs or kwargs['exc_info'] is None:
                exc_info = sys.exc_info()
                if exc_info[0] is not None:
                    kwargs['exc_info'] = exc_info
            super().error(msg, *args, **kwargs)

    # Устанавливаем пользовательский класс логгера
    logging.setLoggerClass(ExcInfoLogger)

    # Создаем логгер для модуля
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.INFO)

    # Определяем форматтер
    class ExceptionFormatter(logging.Formatter):
        def format(self, record):
            result = super().format(record)
            if record.levelno >= logging.WARNING and record.exc_info:
                # Добавляем информацию об исключении
                exception_text = self.formatException(record.exc_info)
                result = f"{result}\n{exception_text}"
            return result

    # Используем ExceptionFormatter
    formatter = ExceptionFormatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s')

    # Создаем обработчики
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    # Добавляем обработчики к логгеру
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger

