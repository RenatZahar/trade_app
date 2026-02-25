# main.py
# после релиза - собрать requirements.txt (pip freeze > requirements.txt)

import time
import os
import sys
from dotenv import load_dotenv
load_dotenv() #загрузка переменных ПЕРЕД загрузкой моих функций

import main_functions as mf

from modules.sql_funcs.moving_txs import moving_txs
from modules.tests.tests_utils_funcs import test_func
from modules.tests.converge_of_elasticnet import converge_of_elasticnet

from config import BLOCKS_SQL_DATA, setup_logging
from modules.finding_price_peaks.get_price_peaks_df import update_peaks

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# from modules.redis_init.redis_init import waiting_for_message
  
# TODO MAIN KEK
# сконцентрироваться на доведение системы в соответствие с скриптом v0.1 
# ПЕРЕНЕСТИ обратно в дб транзакции с 1-2 txs
# перенести в стэш с одной
# протестировать сходимость
# привести проект согласно рекомендациям с chat gpt

# TODO
# NOW:
# поиск причины несходимости модели - ментор?
# внести порог корреляции в настройки модели и в грид парамс
#     threshold = 0.3 
#  conditions = [
#      abs(correlation_matrix.loc['Normalized_sell_amount', 'in_sell_interval']) >= threshold,
#      abs(correlation_matrix.loc['Normalized_buy_amount', 'in_buy_interval']) >= threshold,
#      ]



 
# LONG:
# сделать страницу с доступом к аналитике по моделям (сохранять обучающий дф?)
# сделать доступ (только) по ссылке на код проекта
# вынести в отдельный файл функцию расчета корреляции и скрыть ее с доступа в коде
# написать модуль для сохранения структуры бд в файл (просто визуализацию) и какие индексы присутствуют. можно фиксировать дату последнего анализ и вакуум и запускать их раз в месяц например
# документация 
# надо изучить корреляцию между типами кошельков и импактом в пики для поиска методов ускорения расчетов

# done
# добавил data_operations.py в гит игнор (надо ли?)
# ОПТИМИЗАЦИЯ СКОРОСТИ СБОРА ДАННЫХ ДЛЯ ОБУЧЕНИЯ МОДЕЛИ (в основном - чистка бд от кошельков с 1 и 2 txs) 
# модуль визуализации plotly + flask
# добавил простой (изначальный) способ расчета корреляции
# добавил обучение по гриду параметров
# рефакторинг, упрощение логики

PARSER_TEST = 0
FLASK_TEST = 0 
MAIN_TEST = 0
TEACHING_TEST = 0  #1 or 0.1 
TESTS_FROM_MODULES = 0
PARAM_GRID_TESTING = 0
MOVE_TXS = 0  #добавить в обслуживание бд создание индексов по ТРЕМ столбцам

if __name__ == "__main__": 
   logger = setup_logging(__name__)
   logger.info("Старт main.py")
   # mf.start_redis()
   # mf.start_btc_core_monitor_and_parser()

# МОЖНО ЛИ УСТРОИТЬ ФИЛЬТРАЦИЮ КОШЕЛЬКОВ СРЕДСТВАМИ SQLITE ПЕРЕД РАЗБИЕНИЕМ НА ЧАНКИ - УПРОСТИТ ДАЛЬНЕЙШИЙ РЕФАКТОРИНГ
# ДАННЫЕ ГРЯЗНЫЕ.СМ ФЛАСК ПРАЙС И NSA_ISI_sum
# в светлом будущем протестировать разные decision_threshold для покупок и продаж - но перед этим подготовить код для использования moc данных

   converge_of_elasticnet(TESTS_FROM_MODULES) #можно прописать в main_functions тесты которые надо выполнять переодически и запускать по расписанию

   if MOVE_TXS:
      moving_txs()

   if FLASK_TEST:
      mf.start_flask()

   if MAIN_TEST:
      # проблемы с моделью, не сходится. в чем причина? вроде сделано так же как в 0.1. мб приколы с обьединением по 10и минутным интервалам
      # Objective did not converge. You might want to increase the number of iterations, check the scale of the features or consider increasing regularisation. Duality gap: 5.205e+02, tolerance: 1.568e-01 Linear regression models with null weight for the l1 regularization term are more efficiently fitted using one of the solvers implemented in sklearn.linear_model.Ridge/RidgeCV instead.

      mf.start_flask()
      # mf.clear_all_temp_directory()
      mf.start_btc_price_updater()
      update_peaks() # обновляем раз в день, за вчеращний день. все обучение крутить до вчерашнего дня (не включая сегодня)
      mf.teach_and_update_models(TEACHING_TEST) #запускать в отдельном потоке
      
   if PARAM_GRID_TESTING:
      # сначала распарсиваем файл парам грида и создаем список моделей
      # проверяем на типы корреляции, собираем корреляции в файлы (с учетом параметров корреляции?)
      # потом учим модели по оставшимся элементам грида и собираем результаты в дф
      mf.test_param_grid(TEACHING_TEST)

   
   print('main.py отработал, далее time.sleep(20)')
   while True:
      time.sleep(20)

 

   mf.start_redis()
   mf.start_btc_core_monitor_and_parser()
   mf.teach_and_update_models()

   # у многих функций поток внутри main_func - возможно, имеет смысл перенести их в сюда для контроля

   try:
      while True: 
         time.sleep(10)
   except KeyboardInterrupt:
      print("Завершение работы программы.")

# Существующие индексы в базе:
# (0, 'idx_block_height', 0, 'c', 0)
# (1, 'idx_wallet_id', 0, 'c', 0)

# что такое ZMQ уведомления
# zmqpubrawblock=tcp://127.0.0.1:28334
# zmqpubrawtx=tcp://127.0.0.1:28335
# zmqpubrawblock: Отправляет полные данные о новых блоках.
# zmqpubrawtx: Отправляет полные данные о новых транзакциях.
# Все параметры ZMQ закомментированы, то есть ZMQ-уведомления отключены.
# Рекомендация: Если ваш скрипт может использовать ZMQ для получения уведомлений о новых блоках или транзакциях в реальном времени, вы можете рассмотреть возможность включения этих параметров.

# решить за какое время хранить данные и сделать модуль для удаления старых. и старых логов

# добавить как то глобально адаптеры для sql(?)
# # Регистрация адаптеров
# sqlite3.register_adapter(np.int32, int)
# sqlite3.register_adapter(np.int64, int)

# возможно, надо делать отдельный модуль для взаимодействия с БД. вроде есть библиотека для упрощения sql запросов
#  cursor.execute("PRAGMA locking_mode = EXCLUSIVE;") # отключить при рабочем режиме приложения 
