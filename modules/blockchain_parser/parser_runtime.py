import asyncio
import logging
import threading
import time

from modules.blockchain_parser.main_parser import parser
from modules.btc_core_init.btc_core_manager import blocks_to_download, get_btc_status
from modules.logger.run_tracker import get_current_run_tracker
from modules.logger.runtime_bootstrap import finish_runtime_error
from modules.redis_init.redis_init import (
    get_redis_status,
    send_message,
    start_redis_client,
    waiting_for_message,
)


logger = logging.getLogger("app")

parser_running = False
parser_lock = threading.Lock()


def start_redis():
    status = get_redis_status()
    if status:
        start_redis_client()
        logger.info("Redis успешно запущен и работает.")
        return True

    logger.error("Не удалось запустить Redis.")
    return False


def start_btc_core_monitor_and_parser(
    bitcoin_core_profile="standard",
    restart_bitcoin_core=False,
):
    logger.info("Старт parser_runtime.btc_status_monitor")
    if not start_redis():
        raise RuntimeError("Redis client initialization failed before parser startup.")
    waiting_for_message("check_btc_core_status_line", check_parser_status)
    monitor_thread = threading.Thread(
        target=btc_status_monitor,
        kwargs={
            "bitcoin_core_profile": bitcoin_core_profile,
            "restart_bitcoin_core": restart_bitcoin_core,
        },
    )
    monitor_thread.daemon = True
    monitor_thread.start()


def btc_status_monitor(bitcoin_core_profile="standard", restart_bitcoin_core=False):
    while True:
        btc_status = get_btc_status(
            profile_name=bitcoin_core_profile,
            restart_if_wrong_profile=restart_bitcoin_core,
        )
        new_blocks_in_blockchain = blocks_to_download()
        if btc_status and new_blocks_in_blockchain:
            send_message("check_btc_core_status_line", "btc_core_ready")
        time.sleep(10)


def check_parser_status(message):
    global parser_running
    if message == "btc_core_ready":
        if not parser_running:
            start_blockchain_parser()
        else:
            time.sleep(30)


def run_parser_now_and_wait():
    logger.info("Старт тестового запуска парсера")
    if not start_redis():
        raise RuntimeError("Redis client initialization failed before parser test startup.")
    parser_thread = start_blockchain_parser()
    parser_thread.join()


def start_blockchain_parser():
    global parser_running
    with parser_lock:
        parser_running = True
    parser_thread = threading.Thread(target=run_parser_asyncio)
    parser_thread.start()
    return parser_thread


def run_parser_asyncio():
    global parser_running
    tracker = get_current_run_tracker()
    try:
        asyncio.run(parser())
    except Exception as e:
        logger.error("Ошибка в парсере блокчейна: %s", e)
        finish_runtime_error(tracker, e)
        send_message("parser_status", "completed with error")
    finally:
        with parser_lock:
            parser_running = False
