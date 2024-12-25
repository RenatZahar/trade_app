from dask.distributed import Client, LocalCluster
from dask.config import set as dask_set
from config import setup_logging, DASK_TEMP_DIR

logger = setup_logging(__name__)

def get_dask_client(total_memory='22GB', n_workers=3, threads_per_worker=3, dashboard_address=':8787'):
    # Расчет памяти на воркер
    worker_memory = f"{int(int(total_memory[:-2]) // n_workers)}GB"

    # Настройки Dask для выгрузки данных из оперативной памяти
    dask_set({
        'distributed.worker.memory.target': 0.4,  # Освободить память до 40% от лимита
        'distributed.worker.memory.spill': 0.65,   # Начать выгрузку на диск при % использования
        'distributed.worker.memory.pause': 0.90,  # Приостановить задачи при % использования памяти
        # 'distributed.worker.memory.recent-to-old': 0.4,  # Настройка скорости сброса данных
        'distributed.worker.local-directory': DASK_TEMP_DIR
    })
    
    cluster = LocalCluster(
        n_workers=n_workers,
        threads_per_worker=threads_per_worker,
        memory_limit=worker_memory,  # Предел памяти на одного воркера
        dashboard_address=dashboard_address
    )
    client = Client(cluster)
    logger.info(f"Dask dashboard is running at: {cluster.dashboard_link}")
    
    return client