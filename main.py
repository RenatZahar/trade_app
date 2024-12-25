# main.py
# после релиза - собрать requirements.txt (pip freeze > requirements.txt)

import time
import os
import sys
from dotenv import load_dotenv
load_dotenv() #загрузка переменных ПЕРЕД загрузкой моих функций

import main_functions as mf
from config import BLOCKS_SQL_DATA, setup_logging
from modules.finding_price_peaks.get_price_peaks_df import update_peaks

# from modules.redis_init.redis_init import waiting_for_message
# cначала запускается тот модуль, который подписывается на канал Redis и ждет сообщений

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

# возможно, надо делать отдельный модуль для взаимодействия с БД
# вывод с логгер если нужно записать инфу в лог. в остальных - принт

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
PARSER_TEST = 0
MAIN_TEST = 1
if __name__ == "__main__":
   logger = setup_logging(__name__)
   logger.info("Старт main.py")
   
   if MAIN_TEST == 1:
      mf.start_btc_price_updater()
      update_peaks() # обновляем раз в день, за вчеращний день. все обучение крутить до вчерашнего дня (не включая сегодня)
      mf.teach_and_update_models() #запускать в отдельном потоке

      while True:
         time.sleep(1)

# сохранять транзакции кошельков из даска в бд иначе никак В process_chunk
# ИЛИ В ДАСКЕ ФОРМИРОВАТЬ СРАЗУ ДФ ДЛЯ ОБУЧЕНИЯ
# ФОРМИРОВАТЬ КОРРЕЛЯЦИОННЫЙ ВАЛЛЕТ ДФ 
# А ПОТОМ СОБИРАТЬ ТРАНЗАКЦИИ КОШЕЛЬКОВ ПО ВРЕМЕННЫМ МЕТКАМ

# Существующие индексы в базе:
# (0, 'idx_block_height', 0, 'c', 0)
# (1, 'idx_wallet_id', 0, 'c', 0)


   mf.start_redis()

   
   mf.start_btc_core_monitor_and_parser()
   
   mf.teach_and_update_models()

     #функция обучения моделей с периодами в полтора месяца, сохранения моделей в одну линейку моделей с разными временными промежутками
   # data - папка моделей - папка для обучени новой модели (txt с типом модели и ее параметрами)
   #              |-> название группы моделей - временные рамки модели -  файл (pkl?) модели, txt с ее параметрами, дф с результатами (за больший чем 1,5 месяца период)

   # получаем pkl или txt с параметрами - и запускаем цикл обучения - берем период минус полгода: минус полтора года.....




   # у многих функций поток внутри main_func - возможно, имеет смысл перенести их в сюда для контроля
   # перенос новых модулей осуществлять с доработкой под sql
   # решить за какое время хранить данные и сделать модуль для удаления старых. и старых логов

   try:
      while True:
         time.sleep(1)
   except KeyboardInterrupt:
      print("Завершение работы программы.")
