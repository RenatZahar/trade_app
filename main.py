"""Main entrypoint for local service orchestration.

Operational notes and backlog for this file were moved to:
- docs/main_notes.md
"""

import os
import sys
import time

from dotenv import load_dotenv

import main_functions as mf
from config import setup_logging
from modules.sql_funcs.moving_txs import moving_txs
from modules.tests.converge_of_elasticnet import converge_of_elasticnet
from modules.finding_price_peaks.get_price_peaks_df import update_peaks

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

PARSER_TEST = 0
FLASK_TEST = 0
MAIN_TEST = 0
TEACHING_TEST = 0  # 1 or 0.1
TESTS_FROM_MODULES = 0
PARAM_GRID_TESTING = 0
MOVE_TXS = 0


if __name__ == "__main__":
    logger = setup_logging(__name__)
    logger.info("Старт main.py")

    converge_of_elasticnet(TESTS_FROM_MODULES)

    if MOVE_TXS:
        moving_txs()

    if FLASK_TEST:
        mf.start_flask()

    if MAIN_TEST:
        mf.start_flask()
        mf.start_btc_price_updater()
        update_peaks()
        mf.teach_and_update_models(TEACHING_TEST)

    if PARAM_GRID_TESTING:
        mf.test_param_grid(TEACHING_TEST)

    print("main.py отработал, далее time.sleep(20)")
    while True:
        time.sleep(20)
