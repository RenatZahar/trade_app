# tests_utils_funcs.py

import os
import time
import pandas as pd
import dask.dataframe as dd
from settings.paths import APP_TEMP_DIR, BLOCKS_SQL_DATA

import logging
logger = logging.getLogger("app")
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
module_name_for_temp_dir = __name__.replace('.', '_')

def test_func():
    # перенести в тесты потом 
    # if PARSER_TEST:
    #     print('start tests')
    #     tests.fetch_last_five_rows(BLOCKS_SQL_DATA)
    #     await asyncio.gather(*tasks)
    #     print('end tests')
    #     return

    # ожидаем явное завершение всех задач в tasks! но можно  использовать семафор
    # пока оставил, чтобы сохранить в дб порядок по блокам. мб это не нужно
    pass

