# main.py
# после релиза - собрать requirements.txt (pip freeze > requirements.txt)
import config
import sqlite3
import redis
import threading
import time
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv() #загрузка переменных ПЕРЕД загрузкой моих функций
from config import BLOCKS_SQL_DATA
import main_functions as mf

from config import setup_logging
from modules.redis_init.redis_init import send_message, get_message

from modules.blockchain_parser import main_parser

# from modules.parquet_to_sql_transfer.tranfer_script import transfer_script
# from modules.blocks_db_servises.main_db_servise import main_db_servise

# можно превратить этот апп в вебприложение - как веб приложение обычно взаимиодействует с бэкэндом
# начала запускается тот модуль, который подписывается на канал Redis и ждет сообщений

# МОЖЕТ СДЕЛАТЬ ДВА РЕЖИМА РАБОТЫ? догоняющий - если отстаем больше чем на 2(?) часа, и рабочий, уже в онлайн режиме расчеты 

# что такое ZMQ уведомления
# zmqpubrawblock=tcp://127.0.0.1:28334
# zmqpubrawtx=tcp://127.0.0.1:28335
# zmqpubrawblock: Отправляет полные данные о новых блоках.
# zmqpubrawtx: Отправляет полные данные о новых транзакциях.
# Все параметры ZMQ закомментированы, то есть ZMQ-уведомления отключены.
# Рекомендация: Если ваш скрипт может использовать ZMQ для получения уведомлений о новых блоках или транзакциях в реальном времени, вы можете рассмотреть возможность включения этих параметров.


sys.path.append(os.path.dirname(os.path.abspath(__file__)))


# переписать функцию get_bicoin_prices в async_parser_functions в main_parser
# -28: Загрузка индекса блоков…

# сделал отправку в канал о готовности работы btc core, но не сделал старт парсера после получения сообщения. надо это дело как то по нормальному продумать

# добавить как то глобально адаптеры для sql
# # Регистрация адаптеров
# sqlite3.register_adapter(np.int32, int)
# sqlite3.register_adapter(np.int64, int)
# думаю, надо делать модуль для взаимодействия с БД


PARSER_TEST = 0

if __name__ == "__main__":
   logger = setup_logging(__name__)
   logger.info("Старт main.py")
   mf.start_redis()
   mf.clean_raw_data_and_start_btc_price_updater()


   get_message('check_btc_status_line', mf.start_blockchain_parser)

   mf.start_btc_core_monitor()

        
    # нужны ли доп данные при скачки цен бтс (кроме времени и цены)

    #создаем обьект потока - полезно для его управления и контроля is alive. у остальных функций поток внутри main_func - возможно, имеет смысл перенести их в сюда.


 # сделать start_blockchain_parser после получения статуса от start_btc_core_monitor is online
    

    # перенос новых модулей осуществлять с доработкой под sql
    # добавить скачку курса биткоина и докачку актуального по апи
    # решить за какое время хранить данные и сделать модуль для удаления старых

   try:
      while True:
         time.sleep(1)
   except KeyboardInterrupt:
      print("Завершение работы программы.")



    # async def async_periodic_maintenance(db_path, interval=3600):
    # """
    # Периодически выполняет VACUUM и ANALYZE каждые 'interval' секунд.
    
    # :param db_path: Путь к файлу базы данных SQLite.
    # :param interval: Интервал в секундах между операциями обслуживания.
    # """
    # while True:
    #     await asyncio.sleep(interval)
    #     await async_vacuum_analyze(db_path)