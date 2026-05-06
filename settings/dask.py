from settings.runtime import DASK_TEMP_DIR
from dask.config import set as dask_set
from importlib.metadata import PackageNotFoundError, version


def dask_dataframe_query_planning_setting():
    try:
        dask_version = version("dask")
    except PackageNotFoundError:
        return False

    release_year = int(dask_version.split(".", 1)[0])
    return release_year >= 2025


DASK_SETTINGS = {
    'dataframe.query-planning': dask_dataframe_query_planning_setting(),
    'distributed.worker.memory.target': 0.4,  # Освободить память до 40% от лимита
    'distributed.worker.memory.spill': 0.7,  # Начать выгрузку на диск при % использования
    'distributed.worker.memory.pause': 0.90,  # Приостановить задачи при % использования памяти
    # 'distributed.worker.memory.recent-to-old': 0.4,  # Настройка скорости сброса данных
    'distributed.worker.local-directory': DASK_TEMP_DIR,
    # "dataframe.shuffle.algorithm": "tasks",
    "dataframe.shuffle.method": "disk",
}

DASK_TOTAL_MEMORY = "24GB"
DASK_N_WORKERS = 4
DASK_THREADS_PER_WORKER = 2
DASK_DASHBOARD_ADDRESS = ":8787"


def configure_dask_dataframe_backend():
    dask_set({'dataframe.query-planning': dask_dataframe_query_planning_setting()})


configure_dask_dataframe_backend()
