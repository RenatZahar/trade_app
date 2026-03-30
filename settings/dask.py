from settings.paths import DASK_TEMP_DIR


DASK_SETTINGS = {
        'distributed.worker.memory.target': 0.4,  # Освободить память до 40% от лимита
        'distributed.worker.memory.spill': 0.7,   # Начать выгрузку на диск при % использования
        'distributed.worker.memory.pause': 0.90,  # Приостановить задачи при % использования памяти
        # 'distributed.worker.memory.recent-to-old': 0.4,  # Настройка скорости сброса данных
        'distributed.worker.local-directory': DASK_TEMP_DIR,
        # "dataframe.shuffle.algorithm": "tasks",
        "dataframe.shuffle.method": "disk"
    }