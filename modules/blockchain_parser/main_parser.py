# main_parser.py
import pandas as pd
import time
import asyncio
from pathlib import Path 
import logging
import os
from . import async_parser_functions as apf

BASE_DIR = Path(__file__).resolve().parent
from config import TXS_DIR, CLEARED_PRICES_DIR # type: ignore #переменные подгружаются корректно, проблема в папках
from .config import QUANTITY_OF_BLOCKS_IN_ITERATION, MAX_ITERATIONS, START_BLOCK, PROBLEM_BLOCKS_LIST
# кэш по хэшам не используется в данной версии

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
# вызов функции должен вызываться асинхронно ( asyncio.run(main_parser()) )
async def parser():
    logging.info("Запуск парсера блокчейна")
    last_block = apf.get_existing_last_block(TXS_DIR, START_BLOCK)
    rpc_connection_main = apf.get_rpc_connection(rpc_user, rpc_password, rpc_host, rpc_port)
    all_blocks_to_download = apf.get_list_of_blocks_to_download(last_block, rpc_connection_main)
    blocks_to_parsing_generator = apf.split_list_into_chunks(all_blocks_to_download, QUANTITY_OF_BLOCKS_IN_ITERATION, MAX_ITERATIONS, PROBLEM_BLOCKS_LIST)
    tasks = []
    for blocks_group in blocks_to_parsing_generator:
        start_time = time.time()
        data = await apf.parsing_data(blocks_group)
        print('Данные собраны, сохраняем.')
        min_block_height, max_block_height = apf.get_statistik_data(data)
        save_task = asyncio.create_task(apf.async_save_data_to_parquet(data, min_block_height, max_block_height, TXS_DIR))
        tasks.append(save_task)
        time_of_circle = apf.print_cicle_info(start_time, min_block_height, max_block_height , len(blocks_group), data, QUANTITY_OF_BLOCKS_IN_ITERATION) # type: ignore
        apf.get_avg_blocks_in_minut(time_of_circle)

