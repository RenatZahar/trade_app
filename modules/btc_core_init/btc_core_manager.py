# modules/btc_core_init/btc_core_manager.py

# bitcoin-qt.exe - название процесса для запуска биткоин кор и подкачки блоков
# вход - инит в main
# выход - true что ядро готово к работе, false - не готово (может быть выключенно или подгружать данные)
import psutil
import subprocess
import os
import time
import json
import requests
from bitcoinrpc.authproxy import JSONRPCException
from bitcoinrpc.authproxy import AuthServiceProxy

from config import setup_logging, rpc_user, rpc_password, rpc_host, rpc_port

logger = setup_logging(__name__)

def get_rpc_connection(rpc_user, rpc_password, rpc_host, rpc_port):
    rpc_url = f"http://{rpc_user}:{rpc_password}@{rpc_host}:{rpc_port}"
    # print(rpc_url)
    rpc_connection = AuthServiceProxy(rpc_url, timeout=1200)
    return rpc_connection

def get_btc_status(process_name=os.getenv('BITCOIN_CORE_PROCESS_NAME')):  #функция для вызова из main
    logger.info(f"Старт get_btc_status.")
    while True:
        try:
            rpc_connection = get_rpc_connection(rpc_user, rpc_password, rpc_host, rpc_port)
            break
        except:
            time.sleep(1)

    if is_bitcoin_core_running(process_name):
        btc_core_status = check_ready_btc_core_for_work(rpc_connection)
        return btc_core_status
    else:
        logger.warning(f"{process_name} не запущен. Попытка перезапуска.")
        start_bitcoin_core(rpc_connection)
        return False

def is_bitcoin_core_running(process_name):
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == process_name:
            return True
    logger.info(f"{process_name} не найден в процессах.")
    return False

def start_bitcoin_core(rpc_connection, process_path=os.getenv('BITCOIN_CORE_PATH'), DATA_BLOCKCHAIN_DIR=os.getenv('DATA_BLOCKCHAIN_DIR')):
    # Запуск Bitcoin Core с параметром -datadir
    if not process_path:
        logger.error("Переменная окружения BITCOIN_CORE_PATH не задана.")
        return False
    try:
        subprocess.Popen([process_path, f"-datadir={DATA_BLOCKCHAIN_DIR}"])
        logger.info(f"{process_path} был запущен с параметром -datadir={DATA_BLOCKCHAIN_DIR}.")
        btc_core_status = check_ready_btc_core_for_work(rpc_connection)
        return btc_core_status

    except Exception as e:
        logger.error(f"Не удалось запустить {process_path}: {e}")
        return False

def check_ready_btc_core_for_work(rpc_connection):
    range_ = 30
    for i in range(range_):
        try:
            blockchain_info = rpc_connection.getblockchaininfo()
            if isinstance(blockchain_info, dict):
                # print(blockchain_info)
                return True
            else:
                logger.info('Ожидаем загрузки btc core')
                time.sleep(2)
        except JSONRPCException as e:
            if e.error.get('code') == -28:
                logger.info(f'Ожидаем загрузки btc core: {e.error.get("message")}')
                time.sleep(3)
                if i >= range_//2:
                    time.sleep(10)

            else:
                logger.error(f"Не удалось запустить btc core")
                logger.error(f'Ошибка при попытке получить статус btc core: {e}')
                return False


