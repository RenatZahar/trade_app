# main_parser.py
import pandas as pd
import time
import asyncio
from pathlib import Path 
import os
import sys 
from bitcoinrpc.authproxy import AuthServiceProxy
from modules.redis_init.redis_init import send_message

from . import async_parser_functions as apf
# import tests
from modules.logger.logger import setup_logging
from config import BLOCKS_SQL_DATA, CLEARED_PRICES_DIR, rpc_user, rpc_password, rpc_host, rpc_port # type: ignore #переменные подгружаются корректно, проблема в папках
from .config import QUANTITY_OF_BLOCKS_IN_ITERATION, MAX_ITERATIONS, START_BLOCK, PROBLEM_BLOCKS_LIST
BASE_DIR = Path(__file__).resolve().parent

logger = setup_logging(__name__)

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.max_colwidth', None)
pd.set_option('display.precision', 2)
pd.set_option('display.expand_frame_repr', False)

# print('main_parser.py. убрать кол-во итераций, при скачивании последнего актуального блока - предусмотреть сценарий запуска парсера при появлении нового блока')
# можно через вызов функции сдедать режим на рабочий процесс без кэша (типа если тру - MAX_LINES_IN_TX_CACHE = 0)
# перенести функции обслуживания бд (в начале async_parser_functions) в отдельный модуль
# сохранение кэша в файл не используется в данной версии (async_save_cache_to_file)


# Блок 871747, 1/1
# БОЛЬШАЯ РАЗНИЦА!
# Разница больше 20 процентов

# удалить блок и перезапустить его в работу



async def parser():
    try:
        logger.info("Запуск парсера блокчейна")
        send_message('parser_status', 'working')
        await apf.set_wal_mode(BLOCKS_SQL_DATA)
        last_block = await apf.async_get_existing_last_block(BLOCKS_SQL_DATA, START_BLOCK)
        rpc_connection_main = apf.get_rpc_connection()
        all_blocks_to_download = apf.get_list_of_blocks_to_download(last_block, rpc_connection_main)
        blocks_to_parsing_generator = apf.split_list_into_chunks(all_blocks_to_download, QUANTITY_OF_BLOCKS_IN_ITERATION, MAX_ITERATIONS, PROBLEM_BLOCKS_LIST)
        


        tasks = []
        for blocks_group in blocks_to_parsing_generator:
            if not blocks_group:
                logger.info("Нет блоков для скачки, ожидаем перезапуск")
                send_message('parser_status', 'completed')
                return
            
            start_time = time.time()
            data = await apf.parsing_data(blocks_group)
            if not data.empty:
                min_block_height, max_block_height = apf.get_statistik_data(data)
                save_task = asyncio.create_task(apf.save_data_to_db_with_semaphore(data, BLOCKS_SQL_DATA))
                tasks.append(save_task)
                time_of_circle = apf.print_cicle_info(start_time, min_block_height, max_block_height , len(blocks_group), data, QUANTITY_OF_BLOCKS_IN_ITERATION) # type: ignore
                apf.get_avg_blocks_in_minut(time_of_circle)

                if tasks:
                    await asyncio.gather(*tasks)

        logger.info("Закончились блоки для скачки, ожидаем перезапуск")
        send_message('parser_status', 'completed')
    except Exception as e:
        logger.error("Произошла ошибка: {e}")

