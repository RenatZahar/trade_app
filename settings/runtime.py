#  настройки среды выполнения, пути до нужных элементов окружения

import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv()

def _get_path_from_env(name: str, default: str) -> Path:
    raw_value = os.getenv(name, default)
    normalized = raw_value.strip().strip("'\"")
    return Path(normalized)

rpc_user = os.getenv('RPC_USER')
rpc_password = os.getenv('RPC_PASSWORD')
rpc_host = os.getenv('RPC_HOST')
rpc_port = os.getenv('RPC_PORT')

BITCOIN_CORE_PROCESS_NAME = os.getenv('BITCOIN_CORE_PROCESS_NAME') #через Path, как DASK_TEMP_DIR?
BITCOIN_CORE_PATH = os.getenv('BITCOIN_CORE_PATH')
DATA_BLOCKCHAIN_DIR = (os.getenv('DATA_BLOCKCHAIN_DIR'))

DASK_TEMP_DIR = _get_path_from_env('DASK_TEMP_DIR', 'C:/dask-temp')
BLOCKS_SQL_DATA = _get_path_from_env('BLOCKS_SQL_DATA', 'C:/blocks_sql_data/blocks_sql_data_db.db')

  # Имя процесса Redis для Windows
REDIS_PROCESS_NAME = os.getenv('REDIS_PROCESS_NAME')
REDIS_EXECUTABLE_PATH  = _get_path_from_env('REDIS_EXECUTABLE_PATH', 'C:\\Program Files\\Redis\\redis-server.exe')
