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

import main_functions as mf
from config import BLOCKS_SQL_DATA
from config import setup_logging
from modules.redis_init.redis_init import send_message, get_message
from modules.blockchain_parser import main_parser

# можно превратить этот апп в вебприложение - как веб приложение обычно взаимиодействует с бэкэндом
# cначала запускается тот модуль, который подписывается на канал Redis и ждет сообщений
# МОЖЕТ СДЕЛАТЬ ДВА РЕЖИМА РАБОТЫ? догоняющий - если отстаем больше чем на 2(?) часа, и рабочий, уже в онлайн режиме расчеты 

# что такое ZMQ уведомления
# zmqpubrawblock=tcp://127.0.0.1:28334
# zmqpubrawtx=tcp://127.0.0.1:28335
# zmqpubrawblock: Отправляет полные данные о новых блоках.
# zmqpubrawtx: Отправляет полные данные о новых транзакциях.
# Все параметры ZMQ закомментированы, то есть ZMQ-уведомления отключены.
# Рекомендация: Если ваш скрипт может использовать ZMQ для получения уведомлений о новых блоках или транзакциях в реальном времени, вы можете рассмотреть возможность включения этих параметров.
# добавить как то глобально адаптеры для sql
# # Регистрация адаптеров
# sqlite3.register_adapter(np.int32, int)
# sqlite3.register_adapter(np.int64, int)

# думаю, надо делать модуль для взаимодействия с БД
# вывщд с логгер если нужно записать инфу в лог. в остальных - принт
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
PARSER_TEST = 0

if __name__ == "__main__":
   logger = setup_logging(__name__)
   logger.info("Старт main.py")
   mf.start_redis()

   mf.clean_raw_data_and_start_btc_price_updater()

   get_message('check_btc_status_line', mf.start_blockchain_parser)
   mf.start_btc_core_monitor()
        
   # создаем обьект потока - полезно для его управления и контроля is alive. у остальных функций поток внутри main_func - возможно, имеет смысл перенести их в сюда.
   # перенос новых модулей осуществлять с доработкой под sql
   # решить за какое время хранить данные и сделать модуль для удаления старых. и старых логов

   try:
      while True:
         time.sleep(1)
   except KeyboardInterrupt:
      print("Завершение работы программы.")
