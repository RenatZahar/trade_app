"""Main entrypoint for local service orchestration.

Operational notes and backlog for this file were moved to:
- docs/main_notes.md
"""

import time
from cli_args import parse_args
import modules.logger.logger as app_logger_module
from modules.logger.runtime_bootstrap import (
    finish_runtime_error,
    finish_runtime_interrupted,
    finish_runtime_success,
    start_runtime_logging,
    tracked_stage,
)


if __name__ == "__main__":

    args = parse_args()
    # print(args)

    tracker, logger = start_runtime_logging(args)

    try:
        if args.command == "main-pipeline":
            from modules.finding_price_peaks.get_price_peaks_df import update_peaks
            import main_functions as mf

            mf.warn_data_table_indexes_for_scenario("main_pipeline")
            mf.start_flask()
            mf.start_btc_price_updater()
            update_peaks()
            mf.teach_and_update_models(TEACHING_TEST=0)
            finish_runtime_success(tracker)
            raise SystemExit(0)

        if args.command == "param-grid":
            import main_functions as mf

            mf.warn_data_table_indexes_for_scenario("param_grid")
            mf.test_param_grid(TEACHING_TEST=args.test_fraction, seed=args.seed)
            finish_runtime_success(tracker)
            raise SystemExit(0)
        
        if args.start_parser:
            import main_functions as mf

            mf.warn_data_table_indexes_for_scenario("start_parser")
            mf.start_btc_core_monitor_and_parser()
            while True:
                time.sleep(1)
        
        if args.service == "move_txs":
            from modules.sql_funcs.moving_txs import moving_txs

            with tracked_stage(tracker, "service.move_txs", success_details="move_txs finished"):
                moving_txs()
            finish_runtime_success(tracker)
            raise SystemExit(0)

        if args.service == "move_txs_back":
            from modules.sql_funcs.moving_txs import move_txs_back

            with tracked_stage(tracker, "service.move_txs_back", success_details="move_txs_back finished"):
                move_txs_back()
            finish_runtime_success(tracker)
            raise SystemExit(0)

        if args.command == "test":
            if args.data_test == "downloaded-from-btc-data":
                import main_functions as mf

                mf.warn_data_table_indexes_for_scenario("integration_live.downloaded_from_btc_data")
                mf.run_downloaded_from_btc_data_test_scenario(
                    blocks_count=args.blocks_count,
                    seed=args.seed,
                )
                raise SystemExit(0)



    except KeyboardInterrupt as e:
        finish_runtime_interrupted(tracker, e)
        raise

    except Exception as e:
        finish_runtime_error(tracker, e)
        raise
    finally:
        app_logger_module.stop_logging()








