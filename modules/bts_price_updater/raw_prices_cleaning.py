# app_project\modules\bts_rices_cleaning.py
import time
import pandas as pd
import gzip
from datetime import datetime, timedelta
import os
import sqlite3
from .price_updater import get_price_data
from settings.paths import (
    BLOCKS_SQL_DATA,
    CLEARED_PRICES_DIR,
    RAW_BTC_PRICE_DIR_FILE,
)
from settings.price_peaks import line_time_duration_min as LINE_TIME_DURATION_MIN
import gc

import logging
logger = logging.getLogger("app")

LINE_TIME_DURATION_SEC = LINE_TIME_DURATION_MIN*60
CLEARED_PRICES_NAME_FILE = f"smoothed_BTCUSDT_{LINE_TIME_DURATION_MIN}min.parquet"

def clean_gzip_df(df):
     # print(btc_price_data.to_string())
    df.columns = ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'Taker Buy Quote Asset Volume', 'Taker Buy Base Asset Volume', 'Quote Asset Volume', 'Number of trades']

    # print(f'btc_price_data[Timestamp].max() {btc_price_data['Timestamp'].max()}, end_time {end_time}')
    df.drop(['High', 'Low', 'Volume', 'Taker Buy Quote Asset Volume', 'Taker Buy Base Asset Volume', 'Quote Asset Volume', 'Number of trades'], axis=1, inplace=True)

    df['Price'] = (df['Open'] + df['Close']) / 2
    df.drop(['Open', 'Close'], axis=1, inplace=True)

    df['Price'] = df['Price'].rolling(window=LINE_TIME_DURATION_MIN).mean()
    # Оставляем 1 значение на каждые LINE_TIME_DURATION_MIN минут
    df = df.iloc[::LINE_TIME_DURATION_MIN, :]

    df = df.reset_index(drop=True)
    df.drop([0], axis=0, inplace=True)
    df = df.reset_index(drop=True)

    return df

def clean_downloaded_df(data):
    columns = ['Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close time',
            'Quote asset volume', 'Number of trades', 'Taker buy base asset volume',
            'Taker buy quote asset volume', 'Ignore']

    price_data_df = pd.DataFrame(data, columns=columns)

    price_data_df['Open time'] = pd.to_datetime(price_data_df['Open time'], unit='ms')
    price_data_df['Close time'] = pd.to_datetime(price_data_df['Close time'], unit='ms')

    numeric_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    price_data_df[numeric_columns] = price_data_df[numeric_columns].astype(float)
    price_data_df['Price'] = (price_data_df['Open'] + price_data_df['Close']) / 2

    # Устанавливаем индекс по времени открытия
    price_data_df.set_index('Open time', inplace=True)

   
    resampled_data = price_data_df['Price'].resample(f'{LINE_TIME_DURATION_MIN}min').mean().reset_index()

    resampled_data['Timestamp'] = resampled_data['Open time'].astype('int64') // 10**9

    resampled_data = resampled_data[['Timestamp', 'Price']]
    # print(resampled_data.head())
    return resampled_data

def clean_raw_data():
    logger.info('Старт clean_raw_data')
    conn = sqlite3.connect(BLOCKS_SQL_DATA)
    cursor = conn.cursor()

    # Получение минимального Block_height
    cursor.execute("SELECT MIN(Block_height) FROM data_table;")
    min_block_height = cursor.fetchone()[0]

    # Получение максимального Block_height
    cursor.execute("SELECT MAX(Block_height) FROM data_table;")
    max_block_height = cursor.fetchone()[0]
    if min_block_height is None or max_block_height is None:
        cursor.close()
        conn.close()
        raise RuntimeError("В data_table нет данных для расчета ценового диапазона.")


    cursor.execute("SELECT Block_time FROM data_table WHERE Block_height = ? LIMIT 1;", (min_block_height,))
    min_block_time = cursor.fetchone()[0]

    # Получение Block_time для максимального Block_height
    cursor.execute("SELECT Block_time FROM data_table WHERE Block_height = ? LIMIT 1;", (max_block_height,))
    max_block_time = cursor.fetchone()[0]
    # print(min_block_height, min_block_time, max_block_height, max_block_time)

    conn.close()

    # print(RAW_BTC_PRICE_DIR_FILE.exists())
    # print(RAW_BTC_PRICE_DIR_FILE)
    # Чтение файла и присвоение названий столбцам

    # first_file = first_file.sort
    start_time = min_block_time - LINE_TIME_DURATION_SEC - 60
    end_time = 9000 + LINE_TIME_DURATION_SEC
    full_dir = os.path.join(CLEARED_PRICES_DIR, CLEARED_PRICES_NAME_FILE)

    if os.path.exists(full_dir):
        logger.info(f"Файл {full_dir} существует.")
        btc_price_data = pd.read_parquet(full_dir)
    else:

        with gzip.open(RAW_BTC_PRICE_DIR_FILE, 'rt') as file:
            btc_price_data = pd.read_csv(file, delimiter='|') # type: ignore
            btc_price_data = clean_gzip_df(btc_price_data)


    btc_price_data = btc_price_data[btc_price_data['Timestamp'] >= (start_time)]


    current_time_seconds = int(time.time())
    last_btc_price_data_tmsp = int(btc_price_data.iloc[-1]['Timestamp'])
    start_time_ms = last_btc_price_data_tmsp * 1000
    end_time_ms = current_time_seconds * 1000
    
    start_work_time = time.time() 
    downloaded_price_data = get_price_data(start_time_ms, end_time_ms)
    
    if not downloaded_price_data:
        raise RuntimeError("Не получилось обновить данные BTC из внешнего источника.")
    
    end_work_time = time.time()
    logger.info(f"Завершение get_price_data. Время выполнения: {(end_work_time-start_work_time):.1f} секунд")
    downloaded_price_data = clean_downloaded_df(downloaded_price_data)    
    btc_price_data = pd.concat([btc_price_data, downloaded_price_data], ignore_index=True)

    # Удаляем дубликаты и сортируем
    btc_price_data.drop_duplicates(subset='Timestamp', inplace=True)
    btc_price_data.sort_values('Timestamp', inplace=True)
    btc_price_data.reset_index(drop=True, inplace=True)
    btc_price_data['Human_time'] = pd.to_datetime(btc_price_data['Timestamp'], unit='s')

    current_time = time.time()
    human_readable_time = datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')
    logger.info(f'current time {current_time} ({human_readable_time})')
    btc_price_data.to_parquet(os.path.join(CLEARED_PRICES_DIR, CLEARED_PRICES_NAME_FILE))
    gc.collect()
    logger.info(f"btc_price очищены и сохранены в {CLEARED_PRICES_NAME_FILE}.")
    

