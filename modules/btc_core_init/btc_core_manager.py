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
import sqlite3

from bitcoinrpc.authproxy import JSONRPCException, AuthServiceProxy

from settings.paths import BLOCKS_SQL_DATA
from settings.runtime import (
    BITCOIN_CORE_PATH,
    BITCOIN_CORE_PROCESS_NAME,
    DATA_BLOCKCHAIN_DIR,
    rpc_host,
    rpc_password,
    rpc_port,
    rpc_user,
)
from settings.bitcoin_core import (
    BITCOIN_CORE_SHUTDOWN_TIMEOUT_SEC,
    get_bitcoin_core_config_path,
    normalize_bitcoin_core_profile,
    render_bitcoin_core_config,
    validate_existing_blockchain_datadir,
    write_bitcoin_core_config,
)

import logging
logger = logging.getLogger("app")

def get_rpc_connection(rpc_user, rpc_password, rpc_host, rpc_port):
    rpc_url = f"http://{rpc_user}:{rpc_password}@{rpc_host}:{rpc_port}"
    # print(rpc_url)
    rpc_connection = AuthServiceProxy(rpc_url, timeout=1200)
    return rpc_connection

def get_btc_status(
    process_name=BITCOIN_CORE_PROCESS_NAME,
    profile_name="standard",
    restart_if_wrong_profile=False,
):  #функция для вызова из main
    # logger.info(f"Старт get_btc_status.")
    if is_bitcoin_core_running(process_name):
        if restart_if_wrong_profile and not (
            is_bitcoin_core_running_with_profile(
                process_name,
                profile_name,
                DATA_BLOCKCHAIN_DIR,
            ) and is_bitcoin_core_generated_config_current(
                profile_name,
                DATA_BLOCKCHAIN_DIR,
            )
        ):
            logger.warning(
                "%s запущен не с актуальным профилем %s. "
                "Перезапускаем с управляемым конфигом.",
                process_name,
                profile_name,
            )
            if not stop_bitcoin_core_for_restart(process_name=process_name):
                return False
            return start_bitcoin_core(
                profile_name=profile_name,
                process_path=BITCOIN_CORE_PATH,
                data_blockchain_dir=DATA_BLOCKCHAIN_DIR,
            )
        rpc_connection = get_rpc_connection(rpc_user, rpc_password, rpc_host, rpc_port)
        btc_core_status = check_ready_btc_core_for_work(rpc_connection)
        return btc_core_status
    else:
        if restart_if_wrong_profile:
            logger.warning(
                "%s не запущен. Попытка запуска с управляемым профилем %s.",
                process_name,
                profile_name,
            )
            start_bitcoin_core(
                profile_name=profile_name,
                process_path=BITCOIN_CORE_PATH,
                data_blockchain_dir=DATA_BLOCKCHAIN_DIR,
            )
        else:
            logger.warning(
                "%s не запущен. Попытка запуска со штатным bitcoin.conf.",
                process_name,
            )
            start_bitcoin_core_legacy(
                process_path=BITCOIN_CORE_PATH,
                data_blockchain_dir=DATA_BLOCKCHAIN_DIR,
            )
        return False

def is_bitcoin_core_running(process_name):
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == process_name:
            return True
    logger.info(f"{process_name} не найден в процессах.")
    return False


def get_bitcoin_core_processes(process_name=BITCOIN_CORE_PROCESS_NAME):
    processes = []
    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            if proc.info["name"] == process_name:
                processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return processes


def is_bitcoin_core_running_with_profile(
    process_name,
    profile_name,
    data_blockchain_dir=DATA_BLOCKCHAIN_DIR,
):
    profile = normalize_bitcoin_core_profile(profile_name)
    expected_datadir = str(validate_existing_blockchain_datadir(data_blockchain_dir))
    expected_conf = str(get_bitcoin_core_config_path(profile, expected_datadir))
    for proc in get_bitcoin_core_processes(process_name):
        try:
            cmdline = proc.info.get("cmdline") or proc.cmdline()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        normalized_args = {arg.replace("\\", "/").lower() for arg in cmdline}
        expected_conf_arg = f"-conf={expected_conf}".replace("\\", "/").lower()
        expected_datadir_arg = f"-datadir={expected_datadir}".replace("\\", "/").lower()
        if expected_conf_arg in normalized_args and expected_datadir_arg in normalized_args:
            return True
    return False


def is_bitcoin_core_generated_config_current(
    profile_name,
    data_blockchain_dir=DATA_BLOCKCHAIN_DIR,
):
    profile = normalize_bitcoin_core_profile(profile_name)
    data_dir = validate_existing_blockchain_datadir(data_blockchain_dir)
    expected_conf = get_bitcoin_core_config_path(profile, data_dir)
    if not expected_conf.is_file():
        return False
    try:
        return expected_conf.read_text(encoding="utf-8") == render_bitcoin_core_config(profile)
    except OSError:
        return False


def stop_bitcoin_core_for_restart(
    process_name=BITCOIN_CORE_PROCESS_NAME,
    timeout_sec=BITCOIN_CORE_SHUTDOWN_TIMEOUT_SEC,
):
    processes = get_bitcoin_core_processes(process_name)
    if not processes:
        return True

    try:
        rpc_connection = get_rpc_connection(rpc_user, rpc_password, rpc_host, rpc_port)
        rpc_connection.stop()
        logger.info("Bitcoin Core shutdown requested via RPC stop.")
    except Exception as e:
        logger.error(
            "Не удалось корректно остановить Bitcoin Core через RPC: %s",
            e,
        )
        return False

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if not get_bitcoin_core_processes(process_name):
            logger.info("Bitcoin Core stopped before profile restart.")
            return True
        time.sleep(1)

    logger.error(
        "Bitcoin Core не остановился за %s секунд; принудительно не завершаем процесс.",
        timeout_sec,
    )
    return False


def start_bitcoin_core(
    rpc_connection=None,
    process_path=BITCOIN_CORE_PATH,
    data_blockchain_dir=DATA_BLOCKCHAIN_DIR,
    profile_name="standard",
):
    # Запуск Bitcoin Core с явным -datadir и сгенерированным -conf профилем.
    if not process_path:
        logger.error("Переменная окружения BITCOIN_CORE_PATH не задана.")
        return False
    try:
        data_dir = validate_existing_blockchain_datadir(data_blockchain_dir)
        config_path = write_bitcoin_core_config(profile_name, data_dir)
        subprocess.Popen(
            [
                process_path,
                f"-datadir={data_dir}",
                f"-conf={config_path}",
                "-nosettings",
            ]
        )
        logger.info(
            "%s был запущен: datadir=%s profile=%s conf=%s.",
            process_path,
            data_dir,
            profile_name,
            config_path,
        )
        if rpc_connection is None:
            rpc_connection = get_rpc_connection(rpc_user, rpc_password, rpc_host, rpc_port)
        btc_core_status = check_ready_btc_core_for_work(rpc_connection)
        return btc_core_status

    except Exception as e:
        logger.error(f"Не удалось запустить {process_path}: {e}")
        return False


def start_bitcoin_core_legacy(
    rpc_connection=None,
    process_path=BITCOIN_CORE_PATH,
    data_blockchain_dir=DATA_BLOCKCHAIN_DIR,
):
    # Штатный запуск для основного сценария: настройки берутся из bitcoin.conf
    # внутри datadir, без -conf и без -nosettings.
    if not process_path:
        logger.error("Переменная окружения BITCOIN_CORE_PATH не задана.")
        return False
    try:
        data_dir = validate_existing_blockchain_datadir(data_blockchain_dir)
        subprocess.Popen([process_path, f"-datadir={data_dir}"])
        logger.info(
            "%s был запущен со штатным bitcoin.conf: datadir=%s.",
            process_path,
            data_dir,
        )
        if rpc_connection is None:
            rpc_connection = get_rpc_connection(rpc_user, rpc_password, rpc_host, rpc_port)
        btc_core_status = check_ready_btc_core_for_work(rpc_connection)
        return btc_core_status

    except Exception as e:
        logger.error(f"Не удалось запустить {process_path}: {e}")
        return False

def check_ready_btc_core_for_work(rpc_connection):
    range_ = 60
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
        except Exception as e:
            logger.info(
                "Ожидаем RPC btc core: attempt=%s/%s error=%s",
                i + 1,
                range_,
                e,
            )
            time.sleep(3)
    logger.error("Bitcoin Core RPC не стал доступен за время ожидания.")
    return False
def get_existing_last_block(db_path):
    try:
        with sqlite3.connect(db_path) as db:
            cursor = db.execute("SELECT MAX(Block_height) FROM data_table;")
            result = cursor.fetchone()
            
            if result and result[0] is not None:
                last_block = result[0]
                # logger.info(f"Последний загруженный блок: {last_block}")
            else:
                logger.info(f"База данных блоков пуста")
                last_block = None
            return last_block
    except Exception as e:
        logger.error(f"Ошибка при доступе к базе данных: {e}")
        return None

def blocks_to_download():
    global BLOCKS_SQL_DATA
    rpc_connection = get_rpc_connection(rpc_user, rpc_password, rpc_host, rpc_port)
    current_block = rpc_connection.getblockcount()
    last_downloaded_block = get_existing_last_block(BLOCKS_SQL_DATA)
    if current_block > last_downloaded_block:
        new_blocks = True
    else:
        new_blocks = False
    return new_blocks


