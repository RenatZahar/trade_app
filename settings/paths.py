# общиие пути для модулей

import os
import sys
from pathlib import Path
from price_peaks import line_time_duration_min

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# blockchain sql-data path
BLOCKS_SQL_DATA = BASE_DIR / 'data/blocks_sql_data/blocks_sql_data_db.db'

# dir btc_core
BITCOIN_CORE_PATH = 'C:/Program Files/Bitcoin/bitcoin-qt.exe'
DATA_BLOCKCHAIN_DIR = 'I:/data'

# temps
DASK_TEMP_DIR = 'C:/dask-temp'
APP_TEMP_DIR = 'data/temp'

RAW_BTC_PRICE_DIR_FILE='data/bitcoin_price/raw_btc_price/BTCUSDT.csv.gz'
CLEARED_PRICES_DIR='data/bitcoin_price/cleared_btc_price'
BLOCKS_SQL_DATA='C:/blocks_sql_data/blocks_sql_data_db.db'
BTC_PRICES_WITH_PEAKS_AND_INTERVALS_FILE='data/bitcoin_price/btc_price_df_with_intervals/btc_price_df_with_intervals.parquet'
CLEARED_PRICES_NAME_FILE = f'smoothed_BTCUSDT_{line_time_duration_min}min.parquet'
CLEARED_PRICES_DIR_FILE = CLEARED_PRICES_DIR + '/' + CLEARED_PRICES_NAME_FILE
BTC_PRICES_WITH_PEAKS_AND_INTERVALS_FILE = BASE_DIR / Path(os.getenv('BTC_PRICES_WITH_PEAKS_AND_INTERVALS_FILE', 'data/bitcoin_price/btc_price_df_with_intervals/btc_price_df_with_intervals.parquet'))

TXS_PARQUET_DIR = BASE_DIR / Path(os.getenv('TXS_DIR', 'data/blocks_parquet_data'))
CLEARED_PRICES_DIR = BASE_DIR / Path(os.getenv('CLEARED_PRICES_DIR', 'data/bitcoin_price/cleared_btc_price'))