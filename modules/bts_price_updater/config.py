from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Константы и настройки
SMA_MINUTES = 10
URL = 'https://www.cryptoarchive.com.au/bars/BTCUSDT'
CLEARED_PRICES_NAME_FILE = 'smoothed_BTCUSDT_10min.parquet'
