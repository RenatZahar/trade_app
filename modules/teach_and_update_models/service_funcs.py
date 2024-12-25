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

def get_peaks_df():
    df = pd.read_parquet(BTC_PRICES_WITH_PEAKS_AND_INTERVALS_FILE)
    return df