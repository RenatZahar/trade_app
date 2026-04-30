# main_functions.py

import time
import threading
import asyncio
import os
import json
import logging

from modules.redis_init.redis_init import send_message, waiting_for_message

from settings.paths import NEW_MODELS_PATH
from modules.btc_core_init.btc_core_manager import get_btc_status, blocks_to_download
from modules.blockchain_parser.main_parser  import parser
from modules.redis_init.redis_init import get_redis_status, start_redis_client
from modules.logger.run_tracker import get_current_run_tracker 
from modules.logger import logger as app_logger_module 

logger = logging.getLogger('app')


parser_running = False
parser_lock = threading.Lock()


def warn_data_table_indexes_for_scenario(scenario_name: str) -> None:
    from modules.sql_funcs.moving_txs import warn_required_data_table_indexes
    from settings.paths import BLOCKS_SQL_DATA

    warn_required_data_table_indexes(BLOCKS_SQL_DATA, scenario_name)


# в некоторых случаях парсер отправляет такое сообщение.
#         send_message('parser_status', 'completed with error')
# пока не реализовал перезапуск парсера от этого сообзщения с задержкой


# waiting_for_message('parser_status', start_blockchain_parser)
# Демонические потоки завершатся вместе с завершением программы.
# Недемонические потоки заставят программу дождаться их завершения(например, сохранение данных).
# threading.Thread(target=btc_status_monitor).start()

def start_redis():
    status = get_redis_status()
    if status:
        start_redis_client()
        logger.info("Redis успешно запущен и работает.")
        return True
    else:
        logger.error("Не удалось запустить Redis.")
        return False

def start_btc_price_updater():
    from modules.bts_price_updater.raw_prices_cleaning import clean_raw_data

    clean_raw_data()
    # пока сделал не в отдельном потоке - чтобы пики корректно отработали
    # clean_raw_data_thread = threading.Thread(target=clean_raw_data)
    # clean_raw_data_thread.daemon = True
    # clean_raw_data_thread.start()

def start_btc_core_monitor_and_parser():
    logger.info("Старт mf.btc_status_monitor")
    if not start_redis(): #не нравится конструкция, переписать
        raise RuntimeError("Redis client initialization failed before parser startup.")
    waiting_for_message('check_btc_core_status_line', check_parser_status)
    monitor_thread = threading.Thread(target=btc_status_monitor)
    monitor_thread.daemon = True
    monitor_thread.start()


def btc_status_monitor():
    while True:
        btc_status = get_btc_status()
        new_blocks_in_blockchain = blocks_to_download() #True or False
        if btc_status and new_blocks_in_blockchain:
            send_message('check_btc_core_status_line', 'btc_core_ready')
        time.sleep(10)

def check_parser_status(message):
    global parser_running
    if message == 'btc_core_ready':
        if not parser_running:
            start_blockchain_parser()
        else:
            time.sleep(30)

def run_parser_now_and_wait():
    logger.info("Старт тестового запуска парсера")
    if not start_redis():
        raise RuntimeError("Redis client initialization failed before parser test startup.")
    parser_thread = start_blockchain_parser()
    parser_thread.join()

def start_blockchain_parser():
    global parser_running
    with parser_lock:
        parser_running = True
    parser_thread = threading.Thread(target=run_parser_asyncio)
    parser_thread.start()
    return parser_thread

def run_parser_asyncio():
    global parser_running
    tracker = get_current_run_tracker()
    try:
        asyncio.run(parser())
    except Exception as e:
        logger.error(f"Ошибка в парсере блокчейна: {e}")
        tracker.finish_run('error', e)
        app_logger_module.log_tracker_run_event(tracker, "run_finished", level=logging.ERROR)
        send_message('parser_status', 'completed with error')
    finally:
        with parser_lock:
            parser_running = False


def teach_and_update_models(TEACHING_TEST, seed=None):
    from modules.teach_and_update_models.service_funcs import check_for_new_models
    from modules.teach_and_update_models.orchestrator import teach_model
    from modules.logger.experiment_metadata import summarize_model_metadata
    from modules.logger.runtime_bootstrap import update_runtime_metadata

    resave_json_with_indend()
    model_type_data, model_type, model_info, model_dir_file = check_for_new_models() # type: ignore #возврат str (json или prl) и model_info или pkl модели
    update_runtime_metadata(
        get_current_run_tracker(),
        model_params=summarize_model_metadata(model_type_data, model_type, model_info, model_dir_file),
    )
    teach_model(model_type_data, model_type, model_info, model_dir_file, TEACHING_TEST, seed=seed)
    

def start_flask():
    """Запускает Flask-приложение в отдельном потоке"""
    from modules.flask_module.fl_app import app as flask_app
    startup_error = {}

    def run_flask():
        try:
            flask_app.run(debug=False, host='127.0.0.1', port=5000, use_reloader=False)
        except Exception as e:
            startup_error['exception'] = e
            logger.error(f"Ошибка при запуске Flask: {e}")
            raise
    
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True  # Поток завершится вместе с основной программой
    flask_thread.start()
    time.sleep(1)
    if 'exception' in startup_error:
        raise RuntimeError("Flask startup failed.") from startup_error['exception']
    if not flask_thread.is_alive():
        raise RuntimeError("Flask thread stopped during startup.")
    logger.info("Flask запущен на http://127.0.0.1:5000")
    return flask_thread


def resave_json_with_indend():
    files = [f for f in NEW_MODELS_PATH.iterdir() if f.is_file()]

    # print("Файлы в директории:")
    for file in files:
        if 'example' in file.name:
            continue
        full_dir_file = os.path.join(NEW_MODELS_PATH, file)
        if file.suffix == '.json':
            with open(full_dir_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            with open(full_dir_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

def test_param_grid(TEACHING_TEST, seed=None):
    from modules.teach_and_update_models.orchestrator import teaching_with_param_grid_orchestrator

    teaching_with_param_grid_orchestrator(TEACHING_TEST, seed=seed)


def format_downloaded_from_btc_stage_details(test_summary: dict) -> str:
    details_payload = {
        "requested_blocks": test_summary.get("requested_blocks", []),
        "seed": test_summary.get("seed"),
        "status": test_summary.get("status", "finished"),
        "comparison_status": test_summary.get("comparison_status"),
        "txs_moved": test_summary.get("txs_moved"),
        "low_tx_wallet_max_tx_count": test_summary.get("low_tx_wallet_max_tx_count"),
        "sql_source_tables": test_summary.get("sql_source_tables", []),
        "sql_rows_count": test_summary.get("sql_rows_count", 0),
        "chain_rows_count": test_summary.get("chain_rows_count", 0),
        "absent_blocks_count": test_summary.get("qnt_absent_blocks", 0),
        "absent_blocks": test_summary.get("absent_blocks", []),
        "identical_blocks_count": test_summary.get("identical_blocks_count", 0),
        "identical_blocks": test_summary.get("identical_blocks", []),
        "non_identical_blocks_count": test_summary.get("non_identical_blocks_count", 0),
        "non_identical_blocks": test_summary.get("non_identical_blocks", []),
        "diagnostics_rows_count": test_summary.get("diagnostics_rows_count", 0),
        "diagnostics_records": test_summary.get("diagnostics_records", []),
        "only_in_sql_rows_count": test_summary.get("only_in_sql_rows_count", 0),
        "only_in_btc_rows_count": test_summary.get("only_in_btc_rows_count", 0),
        "sql_compare_parquet": test_summary.get("sql_compare_parquet"),
        "btc_compare_parquet": test_summary.get("btc_compare_parquet"),
        "diagnostics_parquet": test_summary.get("diagnostics_parquet"),
        "only_in_sql_parquet": test_summary.get("only_in_sql_parquet"),
        "only_in_btc_parquet": test_summary.get("only_in_btc_parquet"),
    }
    return json.dumps(details_payload, ensure_ascii=False)


def run_downloaded_from_btc_data_test_scenario(blocks_count: int, seed: int | None = None):
    from tests.integration_live.test_downloaded_from_btc_data import run_downloaded_from_btc_data_test

    tracker = get_current_run_tracker()
    stage_name = "integration_live.test_downloaded_from_btc_data"
    stage_data = tracker.start_stage(stage_name)
    app_logger_module.log_tracker_stage_started(tracker, stage_data)

    try:
        test_summary = run_downloaded_from_btc_data_test(
            blocks_count=blocks_count,
            seed=seed,
        )
    except Exception as e:
        stage_data = tracker.finish_stage('error', details=str(e))
        app_logger_module.log_tracker_stage_finished(tracker, stage_data)
        raise

    if not isinstance(test_summary, dict):
        raise RuntimeError("Downloaded-from-BTC integration test must return a summary dict.")

    details = format_downloaded_from_btc_stage_details(test_summary)
    stage_data = tracker.finish_stage('success', details=details)
    app_logger_module.log_tracker_stage_finished(tracker, stage_data)
    logger.info(
        "Integration/live test finished: test_name=%s requested_blocks=%s absent_blocks=%s identical_blocks=%s non_identical_blocks=%s seed=%s status=%s comparison_status=%s",
        test_summary.get("test_name", "test_downloaded_from_btc_data"),
        test_summary.get("requested_blocks", []),
        test_summary.get("absent_blocks", []),
        test_summary.get("identical_blocks", []),
        test_summary.get("non_identical_blocks", []),
        test_summary.get("seed"),
        test_summary.get("status", "finished"),
        test_summary.get("comparison_status"),
    )
    tracker.finish_run('success')
    app_logger_module.log_tracker_run_event(tracker, "run_finished")
    return test_summary


