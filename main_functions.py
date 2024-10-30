# main_functions.py

import time
import threading
import asyncio
import os
import sys
import asyncio

from dotenv import load_dotenv
from modules.redis_init.redis_init import send_message, get_message

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import setup_logging
from modules.btc_core_init.btc_core_manager import get_btc_status
from modules.blockchain_parser.main_parser  import parser
from modules.bts_price_updater.raw_prices_cleaning import clean_raw_data
from modules.redis_init.redis_init import get_redis_status, start_redis_client


from main import PARSER_TEST


logger = setup_logging(__name__)

parser_running = False
parser_lock = threading.Lock()


def start_redis():
    status = get_redis_status()
    if status:
        start_redis_client()
        logger.info("Redis успешно запущен и работает.")
    else:
        logger.error("Не удалось запустить Redis.")

    

def start_btc_core_monitor():
    btc_status_monitor()
    # пока убрал работу в отдельном потоке 
    # monitor_thread = threading.Thread(target=btc_status_monitor)
    # monitor_thread.daemon = True
    # #Демонические потоки завершатся вместе с завершением программы.
    # # Недемонические потоки заставят программу дождаться их завершения(например, сохранение данных).
    # monitor_thread.start()




def start_blockchain_parser(message):
    def run_parser_asyncio():
        asyncio.run(parser(PARSER_TEST))

    if message == 'ready':
        logger.info("Получено сообщение 'ready' на канале 'btc_status'. Запуск start_blockchain_parser.")
        threading.Thread(target=run_parser_asyncio).start()
        return
    else:
        logger.info(f"Получено сообщение на канале 'btc_status': {message}")

def run_parser():
    try:
        asyncio.run(parser(PARSER_TEST))
    except Exception as e:
        logger.error(f"Ошибка в парсере блокчейна: {e}")




def btc_status_monitor():
    logger.info("Старт mf.btc_status_monitor")
    while True:
        btc_status = get_btc_status()
        if btc_status:
            send_message('check_btc_status_line', 'ready')
            break
        else:
            time.sleep(5)
    # пока не реализовал переодиеский опрос





def clean_raw_data_and_start_btc_price_updater():
    # сделать подгрузку в очищенный дф с ценами с апи бинанса или еще где

    clean_raw_data_thread = threading.Thread(target=clean_raw_data)
    clean_raw_data_thread.daemon = True
    #Демонические потоки завершатся вместе с завершением программы.
    # Недемонические потоки заставят программу дождаться их завершения(например, сохранение данных). По умолчанию все потоки недемонические
    clean_raw_data_thread.start()
    # success = clean_raw_data()
    # if success:
    #     logging.info("Цены биткоина успешно обновлены.")
    # else:
    #     logging.error("Не удалось обновить цены биткоина.")