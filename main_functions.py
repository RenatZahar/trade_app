# main_functions.py

import time
import logging
import threading
import asyncio
from pathlib import Path

from modules.btc_core_init.btc_core_manager import get_btc_status
from modules.blockchain_parser.main_parser  import parser
from modules.bts_price_updater.raw_prices_cleaning import clean_raw_data

def start_btc_core_monitor():
    monitor_thread = threading.Thread(target=btc_status_monitor)
    monitor_thread.daemon = True
    #Демонические потоки завершатся вместе с завершением программы.
    # Недемонические потоки заставят программу дождаться их завершения(например, сохранение данных).
    monitor_thread.start()

def btc_status_monitor():
    logging.info("Старт ma.btc_status_monitor")
    while True:
        btc_status = get_btc_status()
        if btc_status:
            logging.info("Bitcoin Core работает.")
        else:
            logging.error("Bitcoin Core не удалось запустить.")
        time.sleep(60)  # Проверяем статус каждую минуту

def start_blockchain_parser():
    parser_thread = threading.Thread(target=run_parser)
    parser_thread.start()
    return parser_thread

def run_parser():
    try:
        asyncio.run(parser())
    except Exception as e:
        logging.error(f"Ошибка в парсере блокчейна: {e}")

def start_btc_price_updater():
    save_directory = Path(__file__).resolve().parent / 'data' / 'bitcoin_price' / 'updated_btc_price'
    # сделать подгрузку в очищенный дф с ценами с апи бинанса или еще где
    clean_raw_data()
    # success = clean_raw_data()
    # if success:
    #     logging.info("Цены биткоина успешно обновлены.")
    # else:
    #     logging.error("Не удалось обновить цены биткоина.")