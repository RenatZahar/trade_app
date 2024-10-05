# main.py
# после релиза - собрать requirements.txt (pip freeze > requirements.txt)
import config
import sqlite3

import threading
import time
import os
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv() #загрузка переменных ПЕРЕД загрузкой моих функций
from config import BLOCKS_SQL_DATA
# import main_functions as mf
from modules.utils.logging_setup import setup_logging
from modules.blockchain_parser import main_parser
# from modules.parquet_to_sql_transfer.tranfer_script import transfer_script
from modules.parquet_to_sql_transfer.tranfer_script import get_existing_indexes, conn_settings, create_needed_indexes

TEST = 1
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    setup_logging()
    logging.info("Старт main.py")
    print(BLOCKS_SQL_DATA)
    conn = sqlite3.connect(BLOCKS_SQL_DATA)
    cursor = conn.cursor()

    # Вывод первых 5 строк
    table_name = "data_table"  # Замените на название вашей таблицы
    cursor.execute(f"SELECT * FROM {table_name} ORDER BY rowid ASC LIMIT 5;")
    first_rows = cursor.fetchall()
    print("Первые 5 строк:")
    for i in first_rows:
        print(i)



    # Вывод последних 5 строк
    cursor.execute(f"SELECT * FROM {table_name} ORDER BY rowid DESC LIMIT 5;")
    last_rows = cursor.fetchall()
    print("Последние 5 строк:")
    for i in last_rows:
        print(i)

    # Закрытие соединения
    conn.close()




    print('конец скрипта')
    # transfer_script()
    #mf.start_btc_price_updater()
    #mf.start_btc_core_monitor() # сделать start_blockchain_parser после получения статуса от start_btc_core_monitor is online
    #parser_thread = mf.start_blockchain_parser() #создаем обьект потока - полезно для его управления и контроля is alive. у остальных функций поток внутри main_func - возможно, имеет смысл перенести их в сюда.
    

    # перенос новых модулей осуществлять с доработкой под sql
    # добавить скачку курса биткоина и докачку актуального по апи
    # решить за какое время хранить данные и сделать модуль для удаления старых

    # остальная логика приложения :
    time.sleep(600)