# main_functions.py

import time
import threading
import asyncio
import os
import sys
import asyncio

from dotenv import load_dotenv
from modules.redis_init.redis_init import send_message, waiting_for_message

from main import PARSER_TEST
from config import setup_logging
from modules.btc_core_init.btc_core_manager import get_btc_status, blocks_to_download
from modules.blockchain_parser.main_parser  import parser
from modules.bts_price_updater.raw_prices_cleaning import clean_raw_data
from modules.redis_init.redis_init import get_redis_status, start_redis_client
from modules.finding_price_peaks.get_price_peaks_df import get_peaks

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
logger = setup_logging(__name__)

parser_running = False
parser_lock = threading.Lock()


def start_get_peaks():
    get_peaks()


def start_redis():
    status = get_redis_status()
    if status:
        start_redis_client()
        logger.info("Redis успешно запущен и работает.")
    else:
        logger.error("Не удалось запустить Redis.")

def start_btc_core_monitor():
    logger.info("Старт mf.btc_status_monitor")

    waiting_for_message('check_btc_core_status_line', save_btc_core_status)
    monitor_thread = threading.Thread(target=btc_status_monitor)
    monitor_thread.daemon = True
    monitor_thread.start()


# в некоторых случаях парсер отправляет такое сообщение.
#         send_message('parser_status', 'completed with error')
# пока не реализовал перезапуск парсера от этого сообзщения с задержкой


    # waiting_for_message('parser_status', start_blockchain_parser)
    # Демонические потоки завершатся вместе с завершением программы.
    # Недемонические потоки заставят программу дождаться их завершения(например, сохранение данных).
    # threading.Thread(target=btc_status_monitor).start()

def btc_status_monitor():
    while True:
        btc_status = get_btc_status()
        new_blocks_in_blockchain = blocks_to_download() #True or False
        if btc_status and new_blocks_in_blockchain:
            send_message('check_btc_core_status_line', 'btc_core_ready')
        time.sleep(10)

def save_btc_core_status(message):
    global parser_running
    if message == 'btc_core_ready':
        if not parser_running:
            start_blockchain_parser()
        else:
            print('parser working')

def start_blockchain_parser():
    global parser_running
    with parser_lock:
        parser_running = True
    threading.Thread(target=run_parser_asyncio).start()


def run_parser_asyncio():
    global parser_running
    try:
        asyncio.run(parser(PARSER_TEST))
    except Exception as e:
        logger.error(f"Ошибка в парсере блокчейна: {e}")
    finally:
        with parser_lock:
            parser_running = False

# def run_parser():
#     try:
#         asyncio.run(parser(PARSER_TEST))
#     except Exception as e:
#         logger.error(f"Ошибка в парсере блокчейна: {e}")


def clean_raw_data_and_start_btc_price_updater():
    clean_raw_data_thread = threading.Thread(target=clean_raw_data)
    clean_raw_data_thread.daemon = True
    #Демонические потоки завершатся вместе с завершением программы.
    #Недемонические потоки заставят программу дождаться их завершения(например, сохранение данных). По умолчанию все потоки недемонические
    clean_raw_data_thread.start()
