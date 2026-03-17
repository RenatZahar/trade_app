# model.py

import os
import sys
import logging

from pathlib import Path
from config import APP_TEMP_DIR
from logging.handlers import RotatingFileHandler

logger = setup_logging(__name__)
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

script_dir = os.path.dirname(os.path.abspath(__file__))
module_name_for_temp_dir = __name__.replace('.', '_')
dir_for_temp_files_of_module = os.path.join(APP_TEMP_DIR, module_name_for_temp_dir)
os.makedirs(dir_for_temp_files_of_module, exist_ok=True)
os.chdir(script_dir)

def setup_logging(module_name):
    if not os.path.exists(os.path.join(BASE_DIR, 'logs')):
        os.makedirs(os.path.join(BASE_DIR, 'logs'))

    log_file = os.path.join(BASE_DIR, 'logs', f'{module_name}.log')

    # Создаём стандартный логгер
    logger = logging.getLogger(module_name)
    if logger.handlers:  #коммент: убираем дубликаты
        logger.handlers.clear()
    logger.setLevel(logging.INFO)

    # Форматтер для файла
    # file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s')

    # Обработчик для файла
    # file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)

    # file_handler = logging.FileHandler(log_file)
    # file_handler.setFormatter(file_formatter)
    sys.stdout.reconfigure(line_buffering=True)
    # Инициализируем colorama для Windows
    # colorama.init(autoreset=True)

    # Форматтер для консоли
    console_formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s')

    # Обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)

    # Добавляем обработчики к логгеру
    # logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

def modul():
    pass

if __name__ == '__main__':
    modul()
