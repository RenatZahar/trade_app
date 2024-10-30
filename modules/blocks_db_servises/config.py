# config.py

import os
from pathlib import Path
import sys

# Определение базовой директории (app_project)
BASE_DIR = Path(__file__).resolve().parent

# Добавление BASE_DIR в sys.path для импорта модулей
sys.path.append(str(BASE_DIR))

# Указываем путь к базе данных, поднимаясь на два уровня вверх
BLOCKS_SQL_DATA = BASE_DIR.parent.parent / 'data/blocks_sql_data/blocks_sql_data_db.db'


# RAW_BTC_PRICE_DIR_FILE = BASE_DIR / Path(os.getenv('RAW_BTC_PRICE_DIR_FILE', 'data/bitcoin_price/raw_btc_price/BTCUSDT.csv.gz'))
# CLEARED_PRICES_DIR = BASE_DIR / Path(os.getenv('CLEARED_PRICES_DIR', 'data/bitcoin_price/cleared_btc_price'))
