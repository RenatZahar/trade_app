"""Main entrypoint for local service orchestration.

Operational notes and backlog for this file were moved to:
- docs/main_notes.md
"""

import argparse
import time
from modules.logger.run_tracker import RunTracker
import logging
import modules.logger.logger as app_logger_module

EPILOG=(
    "Test modes:\n"
    "  flask         - запустить только Flask\n"
    "  main_pipeline - Flask + updater + peaks + training\n"
    "  param_grid    - запуск подбора параметров\n"
    )

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified entrypoint for trade_app", epilog=EPILOG, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-p", "--start_parser", action="store_true", help="Старт парсера блокчейна")
    parser.add_argument("-t", "--test", choices=["flask", "main_pipeline", "param_grid", "converge_elasticnet", "right_now_test"], help="Тестирование")   
    parser.add_argument("-s", "--service", choices=["move_txs"], help="Сервисные функции")   
    return parser.parse_args()

if __name__ == "__main__":

    args = parse_args()
    tracker = RunTracker(args)
    id_ = tracker.id
    app_logger_module.setup_logging(id_)
    logger = logging.getLogger("app")
    logger.warning(f"Старт main.py, прогон № {id_}")
    app_logger_module.log_tracker_run_event(tracker, "run_started")

    try:
        if args.start_parser:
            import main_functions as mf
            mf.start_btc_core_monitor_and_parser()
            while True:
                time.sleep(1)
        
        if args.service == "move_txs":
            from modules.sql_funcs.moving_txs import moving_txs

            moving_txs()
            tracker.finish_run('success')
            app_logger_module.log_tracker_run_event(tracker, "run_finished")
            raise SystemExit(0)
        
        if args.test == "flask":
            import main_functions as mf

            mf.start_flask()
            tracker.finish_run('success')
            app_logger_module.log_tracker_run_event(tracker, "run_finished")
            raise SystemExit(0)
        
        elif args.test == "main_pipeline":
            from modules.finding_price_peaks.get_price_peaks_df import update_peaks
            import main_functions as mf

            mf.start_flask()
            mf.start_btc_price_updater()
            update_peaks()
            mf.teach_and_update_models(TEACHING_TEST=1)
            tracker.finish_run('success')
            app_logger_module.log_tracker_run_event(tracker, "run_finished")
            raise SystemExit(0)
        
        elif args.test == "param_grid":
            import main_functions as mf

            mf.test_param_grid(TEACHING_TEST=1)
            tracker.finish_run('success')
            app_logger_module.log_tracker_run_event(tracker, "run_finished")
            raise SystemExit(0)
        
        elif args.test == "converge_elasticnet":
            from modules.tests.converge_of_elasticnet import converge_of_elasticnet

            converge_of_elasticnet()
            tracker.finish_run('success')
            app_logger_module.log_tracker_run_event(tracker, "run_finished")
            raise SystemExit(0)
        
        elif args.test == "right_now_test":
            import main_functions as mf
            mf.run_parser_now_and_wait()
            if tracker.status == 'running':
                tracker.finish_run('success')
                app_logger_module.log_tracker_run_event(tracker, "run_finished")
            raise SystemExit(0)

    except KeyboardInterrupt as e:
        tracker.finish_run('interrupted', e)
        app_logger_module.log_tracker_run_event(tracker, "run_finished")
        raise

    except Exception as e:
        tracker.finish_run('error', e)
        app_logger_module.log_tracker_run_event(tracker, "run_finished", level=logging.ERROR)
        raise
    finally:
        app_logger_module.stop_logging()








