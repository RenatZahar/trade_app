# service_funcs.py

import os
import json
import re
import copy
import numpy as np
import itertools

from numpy import append
import pandas as pd
from pathlib import Path 
from datetime import datetime
from sklearn.model_selection import ParameterGrid

from settings.paths import (
    BTC_PRICES_WITH_PEAKS_AND_INTERVALS_FILE,
    NEW_MODELS_PATH,
    NEW_PARAM_GRID_DIR,
    PARAM_GRID_DIR,
    TRAINED_MODELS_DIR,
)
from . import service_funcs as sf
from . import data_operations as do

import logging
logger = logging.getLogger("app")
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

def get_model_type(model_info):
    return model_info['model']['type']

def check_for_new_models():
    if not NEW_MODELS_PATH.exists():
        raise FileNotFoundError(f"Директория с новыми моделями не найдена: {NEW_MODELS_PATH}")

    files = [f for f in NEW_MODELS_PATH.iterdir() if f.is_file()]
    if not files:
        raise FileNotFoundError(f"В директории {NEW_MODELS_PATH} нет файлов моделей для обучения.")

    for file in files:
        if 'example' in file.name:
            continue
        full_dir_file = os.path.join(NEW_MODELS_PATH, file)
        if file.suffix == '.json':
            with open(full_dir_file, 'r', encoding='utf-8') as file:
                model_info = json.load(file)
                model_type = get_model_type(model_info)
                # print(model_type)
            return 'json', model_type, model_info, full_dir_file
        if file.suffix == '.pkl':
            return 'pkl', None, None, None

    raise RuntimeError(f"В директории {NEW_MODELS_PATH} не найден поддерживаемый файл модели.")

def get_peaks_df():
    df = pd.read_parquet(BTC_PRICES_WITH_PEAKS_AND_INTERVALS_FILE)
    df = df.sort_values('Timestamp')
    return df

def move_init_data(model):
    init_file_path = model.init_dir_file
    if init_file_path and init_file_path[-4:] == 'json':
        try:
            # Проверяем, существует ли файл
            init_file_path = Path(init_file_path)
            if init_file_path.exists():
                with open(init_file_path, 'r', encoding='utf-8') as file:
                    init_json_data = json.load(file)
                # Удаляем файл
                init_file_path.unlink()
                logger.info(f"Файл {init_file_path} успешно удалён.")
            else:
                logger.warning(f"Файл {init_file_path} не существует и не может быть удалён.")

            trained_model_json_data = init_json_data.copy()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            trained_model_json_data['model']['train_date'] = timestamp
            trained_model_json_data['model']['profit'] = model.profit_test_df
            model_param_path = model.model_dir / "params_json.json"
            with open(model_param_path, 'w', encoding='utf-8') as f:
                json.dump(trained_model_json_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Произошла ошибка при удалении или создании файла: {e}")    
    else:
        logger.warning('def move_init_data(self).json init file didn"t exist')
        logger.warning(f'init file: {init_file_path}')

def sanitize_filename(filename):
    sanitized = re.sub(r'[<>:"/\\|?*]', '-', filename) # Заменяем недопустимые символы на дефис
    sanitized = sanitized.replace(' ', '_')
    return sanitized


def get_group_of_model_save_dir(model):
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.%f")
    model_dir_name = f"{model.model_type}_{now}"
    sanitized_dir_name = sanitize_filename(model_dir_name)
    model_save_path = Path(TRAINED_MODELS_DIR) / sanitized_dir_name
    return model_save_path


def set_sqlite_pragma(conn):
    """
    Устанавливает оптимальные параметры PRAGMA для улучшения производительности.
    """
    cursor = conn.cursor()
    cursor.execute("PRAGMA synchronous = OFF;")  # Повышает скорость записи, но снижает безопасность
    cursor.execute("PRAGMA journal_mode = WAL;")  # Устанавливает режим WAL для улучшения параллельности чтения/записи
    cursor.execute("PRAGMA cache_size = 300000;")  # Увеличивает размер кэша
    cursor.execute("PRAGMA temp_store = MEMORY;")  # Хранит временные таблицы в памяти
    cursor.execute("PRAGMA threading_mode = Multi;")
    # cursor.execute("PRAGMA locking_mode = EXCLUSIVE;") # отключить при рабочем режиме приложения 
    cursor.execute("PRAGMA locking_mode = NORMAL;") 
    cursor.close()

def get_secs_in_month():
    return 30*24*60*60

def get_secs_in_day():
    return 24*60*60

def get_tmsps_data_of_model(time_params):
    iterations = time_params['iterations']
    max_block_height, last_block_time = do.get_last_block_info()
    profit_test_end_tmsp = 0
    profit_test_start_tmsp = 0
    model_relevance_end_tmsp = 0
    checkpoint_tmsp = last_block_time
    tmsps_of_iterations = {}
    for iter in range(iterations, 0, -1):
        tmsps_of_iterations[iter] = {}
        if time_params['model_relevance_period_months'] and iter == iterations:
            model_relevance_start_tmsp = last_block_time
            model_relevance_end_tmsp = model_relevance_start_tmsp + time_params['model_relevance_period_months']*get_secs_in_month()
            tmsps_of_iterations[iter]['model_relevance_start_tmsp'] = model_relevance_start_tmsp
            tmsps_of_iterations[iter]['model_relevance_end_tmsp'] = model_relevance_end_tmsp
            checkpoint_tmsp = model_relevance_start_tmsp - 1
        else:
            if profit_test_start_tmsp:
                checkpoint_tmsp = profit_test_start_tmsp - 1

        if time_params['profit_test_months']:
            profit_test_end_tmsp = checkpoint_tmsp
            profit_test_start_tmsp = profit_test_end_tmsp - time_params['profit_test_months']*get_secs_in_month()
            tmsps_of_iterations[iter]['profit_test_start_tmsp'] = profit_test_start_tmsp
            tmsps_of_iterations[iter]['profit_test_end_tmsp'] = profit_test_end_tmsp
            checkpoint_tmsp = profit_test_start_tmsp - 1
        if time_params['training_data_duration_months']:
            teaching_end_tmsp = checkpoint_tmsp
            teaching_start_tmsp = teaching_end_tmsp - time_params['training_data_duration_months']*get_secs_in_month()
            tmsps_of_iterations[iter]['teaching_start_tmsp'] = teaching_start_tmsp
            tmsps_of_iterations[iter]['teaching_end_tmsp'] = teaching_end_tmsp
            checkpoint_tmsp = teaching_start_tmsp - 1
        if time_params['time_to_get_cmlt_day']:
            cmlt_end_tmsp = checkpoint_tmsp
            cmlt_start_tmsp = cmlt_end_tmsp - time_params['time_to_get_cmlt_day']*get_secs_in_day()
            tmsps_of_iterations[iter]['cmlt_start_tmsp'] = cmlt_start_tmsp
            tmsps_of_iterations[iter]['cmlt_end_tmsp'] = cmlt_end_tmsp

    return tmsps_of_iterations

def check_for_new_param_grid():
    param_grid_path = Path(NEW_PARAM_GRID_DIR)
    if not param_grid_path.exists():
        raise FileNotFoundError(f"Директория param grid не найдена: {param_grid_path}")

    files_list = [file for file in os.listdir(param_grid_path) if 'example' not in file]
    if not files_list:
        raise FileNotFoundError(f"В директории {param_grid_path} нет файлов param grid для запуска.")

    selected_file = files_list[0]
    path = Path(param_grid_path, selected_file)
    with open(path, 'r', encoding='utf-8') as file:
        json_param_grid = json.load(file)

    time_params = json_param_grid["model"]['time_params']
    grid_params = generate_hierarchical_grid(json_param_grid)
    if not grid_params:
        raise RuntimeError(f"Param grid из файла {path} не содержит ни одной комбинации параметров.")

    return time_params, grid_params

def generate_hierarchical_grid(json_param_grid):
    import itertools
    from sklearn.model_selection import ParameterGrid

    model_config = json_param_grid["model"]

    # Извлекаем тип модели; если не список – оборачиваем в список
    model_types = model_config.get("type", [])
    if not isinstance(model_types, list):
        model_types = [model_types]

    # Теперь параметры лежат на одном уровне: отдельно model_param, time_params, correlation_params и filters
    model_param = transform_params(model_config.get("model_param", {}))           # # изменено: извлекаем model_param напрямую
    time_params = transform_params(model_config.get("time_params", {}))             # # изменено: извлекаем time_params напрямую
    corr_params = transform_params(model_config.get("correlation_params", {}))      # # изменено: извлекаем correlation_params напрямую
    filters_params = transform_params(model_config.get("filters", {}))              # # изменено: извлекаем filters напрямую

    comment = model_config.get("comment", "")

    grid_model_type = list(ParameterGrid({"type": model_types}))
    grid_model_param = list(ParameterGrid(model_param))
    grid_time_params = list(ParameterGrid(time_params))
    grid_corr_params = list(ParameterGrid(corr_params))
    grid_filters = list(ParameterGrid(filters_params))

    all_combinations = list(itertools.product(
        grid_model_type,
        grid_model_param,
        grid_time_params,
        grid_corr_params,
        grid_filters
    ))

    hierarchical_grid = []
    for combo in all_combinations:
        type_dict, model_param_dict, time_params_dict, corr_params_dict, filters_dict = combo
        hierarchical_grid.append({
            "model": {
                "type": type_dict["type"],
                "model_param": model_param_dict,
                "time_params": time_params_dict,
                "correlation_params": corr_params_dict,
                "filters": filters_dict,
                "comment": comment
            }
        })
    return hierarchical_grid


def transform_params(params):
    new_params = {}
    for key, value in params.items():
        if isinstance(value, dict) and "type" in value:
            new_params[key] = generate_values(value)  # # преобразуем dict -> список значений
        else:
            # Если значение уже список – оставляем, иначе оборачиваем в список
            new_params[key] = value if isinstance(value, list) else [value]  # # оборачивание скаляров в список
    return new_params

def generate_values(param):
    # Если параметр описан как словарь с ключом "type", генерируем список значений
    if isinstance(param, dict) and "type" in param:
        if param["type"] == "logspace":
            return np.logspace(param["start"], param["stop"], int(param["num"])).tolist()  # # Используем np.logspace
        elif param["type"] == "linspace":
            return np.linspace(param["start"], param["stop"], int(param["num"])).tolist()    # # Используем np.linspace
    # Если параметр уже является списком или другого типа, возвращаем его как есть
    return param

