# main_functions.py

import time
import threading
import asyncio
import os
import asyncio
import shutil
import json

from modules.redis_init.redis_init import send_message, waiting_for_message

from settings.paths import APP_TEMP_DIR, NEW_MODELS_PATH
from modules.logger.logger import setup_logging
from modules.btc_core_init.btc_core_manager import get_btc_status, blocks_to_download
from modules.blockchain_parser.main_parser  import parser
from modules.bts_price_updater.raw_prices_cleaning import clean_raw_data
from modules.redis_init.redis_init import get_redis_status, start_redis_client
from modules.teach_and_update_models.service_funcs import check_for_new_models
from modules.teach_and_update_models.orchestrator import teach_model, teaching_with_param_grid_orchestrator
from modules.flask_module.fl_app import app as flask_app
logger = setup_logging(__name__)

parser_running = False
parser_lock = threading.Lock()


# в некоторых случаях парсер отправляет такое сообщение.
#         send_message('parser_status', 'completed with error')
# пока не реализовал перезапуск парсера от этого сообзщения с задержкой


# waiting_for_message('parser_status', start_blockchain_parser)
# Демонические потоки завершатся вместе с завершением программы.
# Недемонические потоки заставят программу дождаться их завершения(например, сохранение данных).
# threading.Thread(target=btc_status_monitor).start()

def start_redis():
    status = get_redis_status()
    if status:
        start_redis_client()
        logger.info("Redis успешно запущен и работает.")
    else:
        logger.error("Не удалось запустить Redis.")

def start_btc_price_updater():
    clean_raw_data()
    # пока сделал не в отдельном потоке - чтобы пики корректно отработали
    # clean_raw_data_thread = threading.Thread(target=clean_raw_data)
    # clean_raw_data_thread.daemon = True
    # clean_raw_data_thread.start()

def start_btc_core_monitor_and_parser():
    logger.info("Старт mf.btc_status_monitor")

    waiting_for_message('check_btc_core_status_line', check_parser_status)
    monitor_thread = threading.Thread(target=btc_status_monitor)
    monitor_thread.daemon = True
    monitor_thread.start()


def btc_status_monitor():
    while True:
        btc_status = get_btc_status()
        new_blocks_in_blockchain = blocks_to_download() #True or False
        if btc_status and new_blocks_in_blockchain:
            send_message('check_btc_core_status_line', 'btc_core_ready')
        time.sleep(10)

def check_parser_status(message):
    global parser_running
    if message == 'btc_core_ready':
        if not parser_running:
            start_blockchain_parser()
        else:
            time.sleep(30)

def start_blockchain_parser():
    global parser_running
    with parser_lock:
        parser_running = True
    threading.Thread(target=run_parser_asyncio).start()


def run_parser_asyncio():
    global parser_running
    try:
        asyncio.run(parser())
    except Exception as e:
        logger.error(f"Ошибка в парсере блокчейна: {e}")
    finally:
        with parser_lock:
            parser_running = False


def teach_and_update_models(TEACHING_TEST):
    resave_json_with_indend()
    model_type_data, model_type, model_info, model_dir_file = check_for_new_models() # type: ignore #возврат str (json или prl) и model_info или pkl модели
    teach_model(model_type_data, model_type, model_info, model_dir_file, TEACHING_TEST)
    

def clear_all_temp_directory():
    if not os.path.exists(APP_TEMP_DIR):
        # МБ ПЕРЕНЕСТИ В ОТДЕЛЬНОЕ МЕСТО СОЗДАНИЕ ДИРЕКТОРИЙ? (ВРЕМЕННЫХ ТА И ПРОЧИХ)
        os.makedirs(APP_TEMP_DIR, exist_ok=True)
        return
        
    for filename in os.listdir(APP_TEMP_DIR):
        file_path = os.path.join(APP_TEMP_DIR, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.remove(file_path)  # Удаление файла или символической ссылки
                # print(f"Файл удален: {file_path}")
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)  # Рекурсивное удаление директории
                logger.info(f"Папка удалена: {file_path}")
        except Exception as e:
            logger.error(f"Не удалось удалить {file_path}. Причина: {e}")

def start_flask():
    """Запускает Flask-приложение в отдельном потоке"""
    def run_flask():
        flask_app.run(debug=False, host='127.0.0.1', port=5000, use_reloader=False)
    
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True  # Поток завершится вместе с основной программой
    flask_thread.start()
    logger.info("Flask запущен на http://127.0.0.1:5000")


def resave_json_with_indend():
    files = [f for f in NEW_MODELS_PATH.iterdir() if f.is_file()]

    # print("Файлы в директории:")
    for file in files:
        if 'example' in file.name:
            continue
        full_dir_file = os.path.join(NEW_MODELS_PATH, file)
        if file.suffix == '.json':
            with open(full_dir_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            with open(full_dir_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

def test_param_grid(TEACHING_TEST):
    teaching_with_param_grid_orchestrator(TEACHING_TEST)

def clear_temp_directory_of_module(module_name):
    module_temp_dir = os.path.join(APP_TEMP_DIR, module_name)
    # ОБЬЕДИНИТЬ КАК ТО С КОДОМ СОЗДАНИЯ ДИРЕКТОРИИ ДЛЯ ВРЕМЕННЫХ ФАЙЛЛОВ?
    # ОТДЕЛЬНАЯ ФУНКЦИЯ ДЛЯ СОХРАНЕНИЯ ФАЙЛОВ И УДАЛЕНИЕМ СТАРЫХ ПЕРЕД СОХР НОВЫХ?
    # переделать принты на логгер 
    if not os.path.exists(module_temp_dir):
        return
    
    for filename in os.listdir(module_temp_dir):
        file_path = os.path.join(module_temp_dir, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.remove(file_path)  # Удаление файла или символической ссылки
                # print(f"Файл удален: {file_path}")
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)  # Рекурсивное удаление директории
                logger.info(f"Папка удалена: {file_path}")
        except Exception as e:
            logger.error(f"Не удалось удалить {file_path}. Причина: {e}")
