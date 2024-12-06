# check_for_new_models.py

import os
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from config import setup_logging, BLOCKS_SQL_DATA, NEW_MODELS_PATH, BTC_PRICES_WITH_PEAKS_AND_INTERVALS_FILE

logger = setup_logging(__name__)
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

def get_model_type(model_info):
    return model_info['model']['type']

def check_for_new_models():
    # print(NEW_MODELS_PATH)
    files = [f for f in NEW_MODELS_PATH.iterdir() if f.is_file()]

    # print("Файлы в директории:")
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

def del_json_from_new_models_and_create_new(model):
    init_file_path = Path(model.init_dir_file)
    try:
        # Проверяем, существует ли файл
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
        trained_model_json_data_path = Path(model.model_dir) / f'{model.model_type}_params.json'
        with open(trained_model_json_data_path, 'w') as f:
            json.dump(trained_model_json_data, f, indent=4)
    except Exception as e:
        logger.error(f"Произошла ошибка при удалении или создании файла: {e}")    


def get_peaks_df():
    df = pd.read_parquet(BTC_PRICES_WITH_PEAKS_AND_INTERVALS_FILE)
    return df