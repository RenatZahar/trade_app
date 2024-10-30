import os
from dotenv import load_dotenv
from pathlib import Path
from config import setup_logging
load_dotenv() 

BASE_DIR = Path(__file__).resolve().parent #перенести BASE_DIR в главный конфиг

# Константы и настройки
LINE_TIME_DURATION_MIN = os.getenv('LINE_TIME_DURATION_MIN')
URL = 'https://www.cryptoarchive.com.au/bars/BTCUSDT'
CLEARED_PRICES_NAME_FILE = f'smoothed_BTCUSDT_{LINE_TIME_DURATION_MIN}min.parquet'
