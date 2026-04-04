# model.py

import os
import time
from settings.paths import APP_TEMP_DIR


import logging
logger = logging.getLogger("app")
script_dir = os.path.dirname(os.path.abspath(__file__))
module_name_for_temp_dir = __name__.replace('.', '_')
dir_for_temp_files_of_module = os.path.join(APP_TEMP_DIR, module_name_for_temp_dir)
os.makedirs(dir_for_temp_files_of_module, exist_ok=True)
os.chdir(script_dir)

def modul():
    pass

if __name__ == '__main__':
    modul()

