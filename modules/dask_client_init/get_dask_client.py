# get_dask_client.py
import logging
import time
import os
import json
from dask.distributed import Client, LocalCluster
from dask.config import set as dask_set
from settings.dask import (
    DASK_DASHBOARD_ADDRESS,
    DASK_N_WORKERS,
    DASK_SETTINGS,
    DASK_THREADS_PER_WORKER,
    DASK_TOTAL_MEMORY,
)
from settings.runtime import DASK_TEMP_DIR

logger = logging.getLogger("app")
logging.getLogger("distributed.utils_perf").setLevel(logging.ERROR)
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)


def log_dask_cluster_snapshot(client, label):
    try:
        scheduler_info = client.scheduler_info()
        workers = scheduler_info.get("workers", {})
        worker_summaries = []
        for address, worker_info in workers.items():
            metrics = worker_info.get("metrics", {})
            worker_summaries.append(
                {
                    "address": address,
                    "status": worker_info.get("status"),
                    "nthreads": worker_info.get("nthreads"),
                    "memory_limit": worker_info.get("memory_limit"),
                    "memory": metrics.get("memory"),
                    "managed_bytes": metrics.get("managed_bytes"),
                    "spilled_bytes": metrics.get("spilled_bytes"),
                    "executing": metrics.get("executing"),
                    "in_memory": metrics.get("in_memory"),
                }
            )

        logger.info(
            "DASK_CLUSTER_SNAPSHOT %s",
            json.dumps(
                {
                    "label": label,
                    "worker_count": len(workers),
                    "workers": worker_summaries,
                },
                ensure_ascii=False,
                default=str,
            ),
        )
    except Exception as exc:
        logger.warning("Could not collect Dask cluster snapshot label=%s error=%s", label, exc)


def get_dask_client(total_memory=None, n_workers=None, threads_per_worker=None, dashboard_address=None):
    total_memory = total_memory or DASK_TOTAL_MEMORY
    n_workers = n_workers if n_workers is not None else DASK_N_WORKERS
    threads_per_worker = (
        threads_per_worker
        if threads_per_worker is not None
        else DASK_THREADS_PER_WORKER
    )
    dashboard_address = dashboard_address or DASK_DASHBOARD_ADDRESS

    # Расчет памяти на воркер
    worker_memory = f"{int(int(total_memory[:-2]) // n_workers)}GB"
    logging.getLogger("distributed.utils_perf").setLevel(logging.ERROR)
    logging.getLogger("distributed.worker.memory").setLevel(logging.WARNING)

    # Настройки Dask для выгрузки данных из оперативной памяти
    dask_set(DASK_SETTINGS)
    # dask.config.set({"dataframe.shuffle.method": "disk"})
    logger.info(
        "DASK_CLIENT_PROFILE %s",
        json.dumps(
            {
                "total_memory": total_memory,
                "n_workers": n_workers,
                "threads_per_worker": threads_per_worker,
                "worker_memory": worker_memory,
                "dashboard_address": dashboard_address,
                "local_directory": DASK_TEMP_DIR,
                "settings": DASK_SETTINGS,
            },
            ensure_ascii=False,
            default=str,
        ),
    )
    os.makedirs(DASK_TEMP_DIR, exist_ok=True)

    cluster = LocalCluster(
        n_workers=n_workers,
        threads_per_worker=threads_per_worker,
        memory_limit=worker_memory,  # Предел памяти на одного воркера
        dashboard_address=dashboard_address,
        local_directory=str(DASK_TEMP_DIR),
    )
    client = Client(cluster)
    logger.info(f"Dask dashboard is running at: {cluster.dashboard_link}")
    log_dask_cluster_snapshot(client, "client_started")
    return client

def wait_for_all_tasks(client, poll_interval=1.0, max_checks=300):
    """
    Ожидает, пока в Dask-кластере не останется активных задач.
    """
    for i in range(max_checks):
        scheduler = client.run_on_scheduler(lambda dask_scheduler: dask_scheduler.__dict__.get('tasks', {}))
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

    log_dask_cluster_snapshot(client, "before_close")

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

