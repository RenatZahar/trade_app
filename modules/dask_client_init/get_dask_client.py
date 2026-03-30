# get_dask_client.py
import logging
import time
import os
from dask.distributed import Client, LocalCluster
from dask.config import set as dask_set
from settings.dask import DASK_SETTINGS
from modules.logger.logger import setup_logging
from dask.distributed import wait

logger = setup_logging(__name__)
logging.getLogger("distributed.utils_perf").setLevel(logging.ERROR)
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

def get_dask_client(total_memory='16GB', n_workers=2, threads_per_worker=5, dashboard_address=':8787'):
    # Расчет памяти на воркер
    worker_memory = f"{int(int(total_memory[:-2]) // n_workers)}GB"
    logging.getLogger("distributed.utils_perf").setLevel(logging.ERROR)
    logging.getLogger("distributed.worker.memory").setLevel(logging.ERROR)

    # Настройки Dask для выгрузки данных из оперативной памяти
    dask_set(DASK_SETTINGS)
    # dask.config.set({"dataframe.shuffle.method": "disk"})

    cluster = LocalCluster(
        n_workers=n_workers,
        threads_per_worker=threads_per_worker,
        memory_limit=worker_memory,  # Предел памяти на одного воркера
        dashboard_address=dashboard_address
    )
    client = Client(cluster)
    logger.info(f"Dask dashboard is running at: {cluster.dashboard_link}")
    return client

def close_dask_client_only_futures(client):
    if client:
        # Проверяем, есть ли активные задачи
        active_futures = client.futures
        if active_futures:
            logger.info(f"Ожидание завершения {len(active_futures)} активных задач...")
            wait(active_futures)
            logger.info("Все активные задачи завершены.")

        time.sleep(1)
        client.shutdown()  # Корректная остановка кластера
        client.close()     # Освобождаем сам объект клиента
        logger.info("Dask-клиент успешно закрыт.")
    else:
        logger.warning("Нет активного Dask-клиента для закрытия.")

def wait_for_all_tasks(client, poll_interval=1.0, max_checks=300):
    """
    Ожидает, пока в Dask-кластере не останется активных задач.
    """
    scheduler = client.run_on_scheduler(lambda dask_scheduler: dask_scheduler.__dict__.get('tasks', {}))  # Исправленный способ

    for i in range(max_checks):
        total_tasks = len(scheduler)

        if total_tasks == 0:
            logger.info("Все задачи завершены.")
            return

        logger.info(f"Ожидание завершения {total_tasks} активных задач... Попытка {i+1}/{max_checks}")
        time.sleep(poll_interval)

    logger.warning("Превышено время ожидания всех задач. Возможно, остались зависшие задачи.")


def close_dask_client(client):
    if not client:
        logger.warning("Нет активного Dask-клиента для закрытия.")
        return

    # 1. Ждём завершения всех задач
    wait_for_all_tasks(client)

    # 2. Останавливаем воркеров и выключаем кластер
    try:
        client.retire_workers()
        client.shutdown()
    except Exception as e:
        logger.error(f"Ошибка при завершении кластера: {e}")

    # 3. Закрываем клиент
    try:
        client.close()
        logger.info("Dask-клиент успешно закрыт.")
    except Exception as e:
        logger.error(f"Ошибка при закрытии клиента: {e}")
