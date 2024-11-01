# main_parser.py
import pandas as pd
import time
import asyncio
from pathlib import Path 
import os
import sys 
from bitcoinrpc.authproxy import AuthServiceProxy

from . import async_parser_functions as apf
import tests
from config import setup_logging, BLOCKS_SQL_DATA, CLEARED_PRICES_DIR # type: ignore #переменные подгружаются корректно, проблема в папках
from .config import QUANTITY_OF_BLOCKS_IN_ITERATION, MAX_ITERATIONS, START_BLOCK, PROBLEM_BLOCKS_LIST
BASE_DIR = Path(__file__).resolve().parent

logger = setup_logging(__name__)

rpc_user=os.getenv('RPC_USER')
rpc_password=os.getenv('RPC_PASSWORD')
rpc_host=os.getenv('RPC_HOST')
rpc_port=os.getenv('RPC_PORT')

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.max_colwidth', None)
pd.set_option('display.precision', 2)
pd.set_option('display.expand_frame_repr', False)

print('main_parser.py. убрать кол-во итераций, при скачивании последнего актуального блока - предусмотреть сценарий запуска парсера при появлении нового блока')
# можно через вызов функции сдедать режим на рабочий процесс без кэша (типа если тру - MAX_LINES_IN_TX_CACHE = 0)
# перенести функции обслуживания бд (в начале async_parser_functions) в отдельный модуль
# сохранение кэша в файл не используется в данной версии (async_save_cache_to_file)

async def parser(PARSER_TEST):
    logger.info("Запуск парсера блокчейна")
    await apf.set_wal_mode(BLOCKS_SQL_DATA)
    last_block = await apf.async_get_existing_last_block(BLOCKS_SQL_DATA, START_BLOCK)
    rpc_connection_main = apf.get_rpc_connection()
    all_blocks_to_download = apf.get_list_of_blocks_to_download(last_block, rpc_connection_main)
    blocks_to_parsing_generator = apf.split_list_into_chunks(all_blocks_to_download, QUANTITY_OF_BLOCKS_IN_ITERATION, MAX_ITERATIONS, PROBLEM_BLOCKS_LIST)
    tasks = []
    for blocks_group in blocks_to_parsing_generator:
        start_time = time.time()
        data = await apf.parsing_data(blocks_group)
        min_block_height, max_block_height = apf.get_statistik_data(data)
        save_task = asyncio.create_task(apf.save_data_to_db_with_semaphore(data, BLOCKS_SQL_DATA))
        tasks.append(save_task)
        time_of_circle = apf.print_cicle_info(start_time, min_block_height, max_block_height , len(blocks_group), data, QUANTITY_OF_BLOCKS_IN_ITERATION) # type: ignore
        apf.get_avg_blocks_in_minut(time_of_circle)

        if PARSER_TEST:
            print('start tests')
            tests.fetch_last_five_rows(BLOCKS_SQL_DATA)
            await asyncio.gather(*tasks)
            print('end tests')
            return

        # ожидаем явное завершение всех задач в tasks! но можно  использовать семафор
        # пока оставил, чтобы сохранить в дб порядок по блокам. мб это не нужно
        if tasks:
            await asyncio.gather(*tasks)