# main.py
# после релиза - собрать requirements.txt (pip freeze > requirements.txt)
import config

import threading
import time
import os
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv() #загрузка переменных ПЕРЕД загрузкой моих функций

import main_functions as mf
from modules.utils.logging_setup import setup_logging
# from modules.blockchain_parser import main_parser

TEST = 1
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    setup_logging()
    logging.info("Старт main.py")

    mf.start_btc_price_updater()
    mf.start_btc_core_monitor()
    parser_thread = mf.start_blockchain_parser() #создаем обьект потока - полезно для его управления и контроля is alive. у остальных функций поток внутри main_func - возможно, имеет смысл перенести их в сюда.
    
    # if TEST:
    # else:

    # добавить скачку курсу биткоина и докачку актуального по апи, вероятно
    
    # остальная логика приложения :
    time.sleep(600)