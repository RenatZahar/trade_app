# calculate_corelation.py

import os
import time
from config import setup_logging, BLOCKS_SQL_DATA

logger = setup_logging(__name__)
# BASE_DIR = Path(__file__).resolve().parent
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

def calculate_corelation_main():
    # получаем дф с пиками
    pass



if __name__ == '__main__':
    calculate_corelation_main()
