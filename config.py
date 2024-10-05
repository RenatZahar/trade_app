# config.py

import os
from pathlib import Path
from dotenv import load_dotenv
import sys

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

RAW_BTC_PRICE_DIR_FILE = BASE_DIR / Path(os.getenv('RAW_BTC_PRICE_DIR_FILE', 'data/bitcoin_price/raw_btc_price/BTCUSDT.csv.gz'))
TXS_PARQUET_DIR = BASE_DIR / Path(os.getenv('TXS_DIR', 'data/blocks_parquet_data'))
CLEARED_PRICES_DIR = BASE_DIR / Path(os.getenv('CLEARED_PRICES_DIR', 'data/bitcoin_price/cleared_btc_price'))
BLOCKS_SQL_DATA = BASE_DIR / Path(os.getenv('BLOCKS_SQL_DATA', 'data/blocks_sql_data/blocks_sql_data_db.db'))