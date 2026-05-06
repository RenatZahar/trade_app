# main_parser.py
import pandas as pd
import time
import asyncio
from pathlib import Path 
from collections import deque

from bitcoinrpc.authproxy import AuthServiceProxy
from modules.redis_init.redis_init import send_message
from modules.logger.runtime_bootstrap import tracked_stage
from modules.logger.timing import timed_step

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


PARSER_PROGRESS_WINDOW = 10


def _format_eta(seconds):
    if seconds is None:
        return "unknown"

    total_seconds = max(0, int(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def _build_parser_progress_snapshot(
    *,
    last_range,
    processed_blocks,
    remaining_blocks,
    recent_groups,
):
    recent_blocks = sum(group["blocks"] for group in recent_groups)
    recent_duration_sec = sum(group["duration_sec"] for group in recent_groups)
    recent_blocks_per_min = (
        recent_blocks / (recent_duration_sec / 60)
        if recent_duration_sec > 0
        else None
    )
    eta_seconds = (
        (remaining_blocks / recent_blocks_per_min) * 60
        if recent_blocks_per_min
        else None
    )

    return {
        "last_range": last_range,
        "processed_blocks": processed_blocks,
        "remaining_blocks": remaining_blocks,
        "recent_groups_count": len(recent_groups),
        "recent_blocks": recent_blocks,
        "recent_duration_sec": round(recent_duration_sec, 2),
        "recent_blocks_per_min": (
            round(recent_blocks_per_min, 2)
            if recent_blocks_per_min is not None
            else None
        ),
        "eta": _format_eta(eta_seconds),
    }


def _log_parser_progress(snapshot):
    logger.info(
        "PARSER_PROGRESS last_range=%s processed_blocks=%s remaining_blocks=%s "
        "last_%s_groups_blocks=%s last_%s_groups_duration_sec=%s "
        "last_%s_groups_blocks_per_min=%s eta=%s",
        snapshot["last_range"],
        snapshot["processed_blocks"],
        snapshot["remaining_blocks"],
        snapshot["recent_groups_count"],
        snapshot["recent_blocks"],
        snapshot["recent_groups_count"],
        snapshot["recent_duration_sec"],
        snapshot["recent_groups_count"],
        snapshot["recent_blocks_per_min"],
        snapshot["eta"],
    )



async def parser():
    tracker = get_current_run_tracker()
    try:
        logger.info("Запуск парсера блокчейна")
        send_message('parser_status', 'working')

        prepare_stage_details = None
        with tracked_stage(
            tracker,
            'parser.prepare_download_list',
            success_details=lambda: prepare_stage_details,
        ):
            await apf.set_wal_mode(BLOCKS_SQL_DATA)
            last_block = await apf.async_get_existing_last_block(BLOCKS_SQL_DATA, START_BLOCK)
            rpc_connection_main = apf.get_rpc_connection()
            all_blocks_to_download = apf.get_list_of_blocks_to_download(last_block, rpc_connection_main)
            blocks_to_parsing_generator = apf.split_list_into_chunks(all_blocks_to_download, QUANTITY_OF_BLOCKS_IN_ITERATION, MAX_ITERATIONS, PROBLEM_BLOCKS_LIST)
            prepare_stage_details = f'blocks_to_download={len(all_blocks_to_download)}'
        


        tasks = []
        processed_blocks = 0
        recent_groups = deque(maxlen=PARSER_PROGRESS_WINDOW)
        total_blocks_to_download = len(all_blocks_to_download)
        for blocks_group in blocks_to_parsing_generator:
            if not blocks_group:
                logger.info("Нет блоков для скачки, ожидаем перезапуск")
                send_message('parser_status', 'completed')
                return
            
            start_time = time.time()
            stage_started_perf_counter = time.perf_counter()
            process_stage_details = None
            with tracked_stage(
                tracker,
                'parser.process_blocks_group',
                success_details=lambda: process_stage_details,
            ):
                with timed_step("parser.process_blocks_group.parsing_data", blocks=blocks_group) as timing:
                    data = await apf.parsing_data(blocks_group)
                    timing["df_rows"] = len(data)
                if not data.empty:
                    with timed_step("parser.process_blocks_group.stats", blocks=blocks_group) as timing:
                        min_block_height, max_block_height = apf.get_statistik_data(data)
                        timing["min_block"] = min_block_height
                        timing["max_block"] = max_block_height
                    save_task = asyncio.create_task(apf.save_data_to_db_with_semaphore(data, BLOCKS_SQL_DATA))
                    tasks.append(save_task)
                    with timed_step("parser.process_blocks_group.cycle_info", blocks=blocks_group):
                        time_of_circle = apf.print_cicle_info(start_time, min_block_height, max_block_height , len(blocks_group), data, QUANTITY_OF_BLOCKS_IN_ITERATION) # type: ignore
                    apf.get_avg_blocks_in_minut(time_of_circle)

                    if tasks:
                        with timed_step("parser.process_blocks_group.save_wait", blocks=blocks_group, df_rows=len(data)):
                            await asyncio.gather(*tasks)
                            tasks.clear()

                    process_stage_details = f'blocks={len(blocks_group)} range={min_block_height}-{max_block_height}'

                    stage_duration_sec = time.perf_counter() - stage_started_perf_counter
                    processed_blocks += len(blocks_group)
                    recent_groups.append(
                        {
                            "blocks": len(blocks_group),
                            "duration_sec": stage_duration_sec,
                        }
                    )
                    remaining_blocks = max(total_blocks_to_download - processed_blocks, 0)
                    progress_snapshot = _build_parser_progress_snapshot(
                        last_range=f"{min_block_height}-{max_block_height}",
                        processed_blocks=processed_blocks,
                        remaining_blocks=remaining_blocks,
                        recent_groups=list(recent_groups),
                    )
                    _log_parser_progress(progress_snapshot)


                else:
                    process_stage_details = f'blocks={len(blocks_group)} data_is_empty'
                    processed_blocks += len(blocks_group)

        logger.info("Закончились блоки для скачки, ожидаем перезапуск")
        send_message('parser_status', 'completed')
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}")
        raise


