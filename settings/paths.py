# общиие пути для модулей/проекта

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# dir моделей
NEW_MODELS_PATH = BASE_DIR / 'data/models/new_models'
TRAINED_MODELS_DIR = BASE_DIR / 'data/models/trained_models'

CLEARED_PRICES_DIR = BASE_DIR / 'data/bitcoin_price/cleared_btc_price'

RAW_BTC_PRICE_DIR_FILE = BASE_DIR / 'data/bitcoin_price/raw_btc_price/BTCUSDT.csv.gz'
BTC_PRICES_WITH_PEAKS_AND_INTERVALS_FILE = BASE_DIR / 'data/bitcoin_price/btc_price_df_with_intervals/btc_price_df_with_intervals.parquet'

TXS_PARQUET_DIR = BASE_DIR / 'data/blocks_parquet_data'


APP_TEMP_DIR = BASE_DIR / 'data/temp'

PARAM_GRID_DIR = BASE_DIR / 'data/param_grids'
NEW_PARAM_GRID_DIR = PARAM_GRID_DIR / 'new_grids'
PARAM_GRID_RESULTS = PARAM_GRID_DIR / 'param_grid_results'

BLOCKS_SQL_DATA = BASE_DIR / 'data/blocks_sql_data/blocks_sql_data_db.db' #это же старая настройка? сейчас ее надо хранить в рантайм


BLOCK_HEIGHT_BLOCK_TIME_MAP_DIR_FILE = BASE_DIR / 'data/block_height_block_time_map/map.parquet'

# эти нужны?
# TXS_PARQUET_DIR = BASE_DIR / Path(os.getenv('TXS_DIR', 'data/blocks_parquet_data'))
# CLEARED_PRICES_DIR = BASE_DIR / Path(os.getenv('CLEARED_PRICES_DIR', 'data/bitcoin_price/cleared_btc_price'))



