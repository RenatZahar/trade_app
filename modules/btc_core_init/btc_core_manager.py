# modules/btc_core_init/btc_core_manager.py

# bitcoin-qt.exe - название процесса для запуска биткоин кор и подкачки блоков
# вход - инит в main
# выход - true что ядро готово к работе, false - не готово (может быть выключенно или подгружать данные)
import psutil
import subprocess
import logging
import os

def get_btc_status(process_name=os.getenv('BITCOIN_CORE_PROCESS_NAME')):  #функция для вызова из main
    logging.info(f"Старт get_btc_status.")
    if is_bitcoin_core_running(process_name):
        return True
    else:
        logging.warning(f"{process_name} не запущен. Попытка перезапуска.")
        return start_bitcoin_core()

def is_bitcoin_core_running(process_name):
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == process_name:
            return True
    logging.info(f"{process_name} не найден в процессах.")
    return False

def start_bitcoin_core(process_path = os.getenv('BITCOIN_CORE_PATH')):
    """Запускает процесс Bitcoin Core."""
    try:
        subprocess.Popen([process_path])
        logging.info(f"{process_path} был запущен.")
        return True
    except Exception as e:
        logging.error(f"Не удалось запустить {process_path}: {e}")
        return False
