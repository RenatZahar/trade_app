#  настройки среды выполнения, пути до нужных элементов окружения

import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv()

rpc_user = os.getenv('RPC_USER')
rpc_password = os.getenv('RPC_PASSWORD')
rpc_host = os.getenv('RPC_HOST')
rpc_port = os.getenv('RPC_PORT')

BITCOIN_CORE_PROCESS_NAME = os.getenv('BITCOIN_CORE_PROCESS_NAME') #через Path, как DASK_TEMP_DIR?
BITCOIN_CORE_PATH = os.getenv('BITCOIN_CORE_PATH')
DATA_BLOCKCHAIN_DIR = (os.getenv('DATA_BLOCKCHAIN_DIR'))

DASK_TEMP_DIR = Path(os.getenv('DASK_TEMP_DIR', 'C:/dask-temp'))

  # Имя процесса Redis для Windows
REDIS_PROCESS_NAME = os.getenv('REDIS_PROCESS_NAME')
REDIS_EXECUTABLE_PATH  = Path(os.getenv('REDIS_EXECUTABLE_PATH', 'C:\\Program Files\\Redis\\redis-server.exe'))