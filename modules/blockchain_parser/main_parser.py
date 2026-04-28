# main_parser.py
import pandas as pd
import time
import asyncio
from pathlib import Path 

from bitcoinrpc.authproxy import AuthServiceProxy
from modules.redis_init.redis_init import send_message
import modules.logger.logger as app_logger_module

from . import async_parser_functions as apf
# import tests
from modules.logger.run_tracker import get_current_run_tracker
from settings.runtime import rpc_user, rpc_password, rpc_host, rpc_port
from settings.paths import BLOCKS_SQL_DATA, CLEARED_PRICES_DIR # type: ignore #переменные подгружаются корректно, проблема в папках
from settings.parser import QUANTITY_OF_BLOCKS_IN_ITERATION, MAX_ITERATIONS, START_BLOCK, PROBLEM_BLOCKS_LIST
BASE_DIR = Path(__file__).resolve().parent

import logging
logger = logging.getLogger("app")

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.max_colwidth', None)
pd.set_option('display.precision', 2)
pd.set_option('display.expand_frame_repr', False)

# print('main_parser.py. убрать кол-во итераций, при скачивании последнего актуального блока - предусмотреть сценарий запуска парсера при появлении нового блока')
# можно через вызов функции сдедать режим на рабочий процесс без кэша (типа если тру - MAX_LINES_IN_TX_CACHE = 0)
# перенести функции обслуживания бд (в начале async_parser_functions) в отдельный модуль


# Блок 871747, 1/1
# БОЛЬШАЯ РАЗНИЦА!
# Разница больше 20 процентов

# удалить блок и перезапустить его в работу



async def parser():
    tracker = get_current_run_tracker()
    try:
        logger.info("Запуск парсера блокчейна")
        send_message('parser_status', 'working')

        stage_data = tracker.start_stage('parser.prepare_download_list')
        app_logger_module.log_tracker_stage_started(tracker, stage_data)

        await apf.set_wal_mode(BLOCKS_SQL_DATA)
        last_block = await apf.async_get_existing_last_block(BLOCKS_SQL_DATA, START_BLOCK)
        rpc_connection_main = apf.get_rpc_connection()
        all_blocks_to_download = apf.get_list_of_blocks_to_download(last_block, rpc_connection_main)
        blocks_to_parsing_generator = apf.split_list_into_chunks(all_blocks_to_download, QUANTITY_OF_BLOCKS_IN_ITERATION, MAX_ITERATIONS, PROBLEM_BLOCKS_LIST)

        stage_data = tracker.finish_stage('success', details=f'blocks_to_download={len(all_blocks_to_download)}')
        app_logger_module.log_tracker_stage_finished(tracker, stage_data)
        


        tasks = []
        for blocks_group in blocks_to_parsing_generator:
            if not blocks_group:
                logger.info("Нет блоков для скачки, ожидаем перезапуск")
                send_message('parser_status', 'completed')
                return
            
            stage_data = tracker.start_stage('parser.process_blocks_group')
            app_logger_module.log_tracker_stage_started(tracker, stage_data)
            
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

                stage_data = tracker.finish_stage(
                    'success',
                    details=f'blocks={len(blocks_group)} range={min_block_height}-{max_block_height}',
                )
                app_logger_module.log_tracker_stage_finished(tracker, stage_data)


            stage_data = tracker.finish_stage('success', details=f'blocks={len(blocks_group)} data_is_empty')
            app_logger_module.log_tracker_stage_finished(tracker, stage_data)

        logger.info("Закончились блоки для скачки, ожидаем перезапуск")
        send_message('parser_status', 'completed')
    except Exception as e:
        stage_data = tracker.finish_stage('error', details=str(e))
        app_logger_module.log_tracker_stage_finished(tracker, stage_data)
        logger.error(f"Произошла ошибка: {e}")
        raise


