# teach_models.py

import os
import time
import pandas as pd
from config import setup_logging, BLOCKS_SQL_DATA, BTC_PRICES_WITH_PEAKS_AND_INTERVALS_FILE
from modules.teach_and_update_models.service_funcs import del_json_from_new_models_and_create_new

from . import model_classes as mc


logger = setup_logging(__name__)
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

def teach_model(model_type, model_info, init_dir_file):
    if model_type == 'ElasticNet':
        model = mc.ElasticNetModel(model_info, init_dir_file = init_dir_file)
        model.train_with_iterations()

    else:
        raise ValueError(f"Модель типа {model_type} не поддерживается.") 
    
    del_json_from_new_models_and_create_new(model)
    


#удалять json после получения pkl. а лучше - переносить их в другую папку teached_models 

# if __name__ == '__main__':
#     teach_models()
