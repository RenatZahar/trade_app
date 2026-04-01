"""Main entrypoint for local service orchestration.

Operational notes and backlog for this file were moved to:
- docs/main_notes.md
"""

import argparse
import os

import main_functions as mf
from modules.logger.logger import setup_logging
from modules.sql_funcs.moving_txs import moving_txs
from modules.tests.converge_of_elasticnet import converge_of_elasticnet
from modules.finding_price_peaks.get_price_peaks_df import update_peaks

EPILOG=(
    "Test modes:\n"
    "  flask         - запустить только Flask\n"
    "  main_pipeline - Flask + updater + peaks + training\n"
    "  param_grid    - запуск подбора параметров\n"
    )



def run_parser():
    mf.start_btc_core_monitor_and_parser()

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified entrypoint for trade_app", epilog=EPILOG, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-p", "--start_parser", action="store_true", help="Старт парсера блокчейна")
    parser.add_argument("-t", "--test", choices=["flask", "main_pipeline", "param_grid", "converge_elasticnet"], help="Тестирование")   
    parser.add_argument("-s", "--service", choices=["move_txs"], help="Сервисные функции")   
    return parser.parse_args()

if __name__ == "__main__":
    logger = setup_logging(__name__)
    logger.info("Старт main.py")

    args = parse_args()
    if args.start_parser:
        run_parser()
        raise SystemExit(0)
    
    if args.service == "move_txs":
        moving_txs()
        raise SystemExit(0)
    
    if args.test == "flask":
        mf.start_flask()
        raise SystemExit(0)
    elif args.test == "main_pipeline":
        mf.start_flask()
        mf.start_btc_price_updater()
        update_peaks()
        mf.teach_and_update_models(TEACHING_TEST=1)
        raise SystemExit(0)
    elif args.test == "param_grid":
        mf.test_param_grid(TEACHING_TEST=1)
        raise SystemExit(0)
    elif args.test == "converge_elasticnet":
        converge_of_elasticnet()
        raise SystemExit(0)
    





