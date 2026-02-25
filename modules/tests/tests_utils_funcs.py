# tests_utils_funcs.py

import os
import time
import pandas as pd
import dask.dataframe as dd
from config import setup_logging, BLOCKS_SQL_DATA, APP_TEMP_DIR

logger = setup_logging(__name__)
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
module_name_for_temp_dir = __name__.replace('.', '_')
dir_for_temp_files_of_module = os.path.join(APP_TEMP_DIR, module_name_for_temp_dir)
# os.makedirs(dir_for_temp_files_of_module, exist_ok=True)

def test_func():
    print(script_dir)
    print(dir_for_temp_files_of_module)


def save_parquet(temp_name_for_files_dir):
    pass

def load_parquet(temp_name_for_files_dir):
    pass 

def check_pandas_obj_type(obj):
    if isinstance(obj, pd.DataFrame):
        # return dd.from_pandas(obj, npartitions=npartitions)
        return pd.DataFrame
    elif isinstance(obj, str):
        return str