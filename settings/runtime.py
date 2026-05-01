#  настройки среды выполнения, пути до нужных элементов окружения

import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv()


class RuntimeConfigError(RuntimeError):
    """Raised when runtime configuration is incomplete for a scenario."""


def _get_path_from_env(name: str, default: str) -> Path:
    raw_value = os.getenv(name, default)
    normalized = raw_value.strip().strip("'\"")
    return Path(normalized)


def required_env_names_for(dependency_names):
    from settings.runtime_contracts import REQUIRED_ENV_BY_DEPENDENCY

    required_names = []
    for dependency_name in dependency_names:
        if dependency_name not in REQUIRED_ENV_BY_DEPENDENCY:
            raise RuntimeConfigError(f"Unknown runtime dependency: {dependency_name}")

        for env_name in REQUIRED_ENV_BY_DEPENDENCY[dependency_name]:
            if env_name not in required_names:
                required_names.append(env_name)
    return tuple(required_names)


def validate_required_env(env_names, environ=None):
    source = os.environ if environ is None else environ
    missing_names = [
        env_name
        for env_name in env_names
        if not str(source.get(env_name, "")).strip()
    ]
    if missing_names:
        formatted_names = ", ".join(missing_names)
        raise RuntimeConfigError(
            f"Missing required environment variables: {formatted_names}"
        )
    return tuple(env_names)


def validate_runtime_dependencies(dependency_names, environ=None):
    required_names = required_env_names_for(dependency_names)
    validate_required_env(required_names, environ=environ)
    return required_names


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
