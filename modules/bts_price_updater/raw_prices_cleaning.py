# app_project\modules\bts_price_updater\raw_prices_cleaning.py

import pandas as pd
import gzip
from datetime import datetime, timedelta
import os
import logging
from dotenv import load_dotenv

load_dotenv()
from config import RAW_BTC_PRICE_DIR_FILE, TXS_DIR, CLEARED_PRICES_DIR # type: ignore #переменные подгружаются корректно, проблема в папках

from .config import SMA_MINUTES, CLEARED_PRICES_NAME_FILE

def clean_raw_data():
    if not os.listdir(CLEARED_PRICES_DIR):
        print(TXS_DIR)
        list_of_files_with_txs = os.listdir(TXS_DIR)
        first_file = list_of_files_with_txs[0]
        print('raw_prices_cleaning. убедиться, что сортировка не нужна. мб нужно явно взять файл с наименьшим номером')
        print('raw_prices_cleaning. возможно, надо брать среднее не за 10 значений, а среднее за предыдущие 10')

        # first_file = first_file.sort
        oldest_txs = pd.read_parquet(os.path.join(TXS_DIR, first_file))
        start_time = oldest_txs.iloc[0]['Block_time'] - 1200

        last_file = list_of_files_with_txs[-1]
        newest_txs = pd.read_parquet(os.path.join(TXS_DIR, last_file))
        end_time = newest_txs.iloc[-1]['Block_time'] + 1200

        print(RAW_BTC_PRICE_DIR_FILE.exists())
        print(RAW_BTC_PRICE_DIR_FILE)
        # Чтение файла и присвоение названий столбцам
        with gzip.open(RAW_BTC_PRICE_DIR_FILE, 'rt') as file:
            btc_price_data = pd.read_csv(file, delimiter='|')

        # print(btc_price_data.to_string())

        btc_price_data.columns = ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'Taker Buy Quote Asset Volume', 'Taker Buy Base Asset Volume', 'Quote Asset Volume', 'Number of trades']
        # df.drop_duplicates(subset=['Timestamp'], keep='first', inplace=True)
        btc_price_data.drop(['High', 'Low', 'Volume', 'Taker Buy Quote Asset Volume', 'Taker Buy Base Asset Volume', 'Quote Asset Volume'], axis=1, inplace=True)

        # Расчет среднего между High и Low и добавление его в новый столбец Price
        btc_price_data['Price'] = (btc_price_data['Open'] + btc_price_data['Close']) / 2

        # Удаление столбцов High и Low
        btc_price_data.drop(['Open', 'Close'], axis=1, inplace=True)


        btc_price_data['SMA_10_MINUTES'] = btc_price_data['Price'].rolling(window=SMA_MINUTES).mean()
        # Оставляем 1 значение на каждые 10 минут
        btc_price_data = btc_price_data.iloc[::SMA_MINUTES, :]
        btc_price_data = btc_price_data.reset_index(drop=True)

        # Время в секундах для двух лет и двух месяцев

        btc_price_data = btc_price_data[btc_price_data['Timestamp'] >= (start_time)]
        btc_price_data = btc_price_data[btc_price_data['Timestamp'] <= (end_time)]
        btc_price_data['Human_time'] = pd.to_datetime(btc_price_data['Timestamp'], unit='s')


        btc_price_data.to_parquet(os.path.join(CLEARED_PRICES_DIR, CLEARED_PRICES_NAME_FILE))
        logging.info(f"cleared btc_price_data был сохранен.")
    
