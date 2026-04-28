"""Main entrypoint for local service orchestration.

Operational notes and backlog for this file were moved to:
- docs/main_notes.md
"""

import argparse
import time
from modules.logger.run_tracker import RunTracker
import logging
import modules.logger.logger as app_logger_module

def warn_data_table_indexes_for_scenario(scenario_name: str) -> None:
    from modules.sql_funcs.moving_txs import warn_required_data_table_indexes
    from settings.paths import BLOCKS_SQL_DATA

    warn_required_data_table_indexes(BLOCKS_SQL_DATA, scenario_name)


EPILOG=(
    "Test modes:\n"
    "  flask         - запустить только Flask\n"
    "  main_pipeline - Flask + updater + peaks + training\n"
    "  param_grid    - запуск подбора параметров\n"
    "\n"
    "Integration live tests:\n"
    "  test_downloaded_from_btc_data - сравнение SQL-данных с повторной реконструкцией из BTC RPC\n"
    )

def validate_cli_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    active_top_level_modes = [
        args.start_parser,
        args.service is not None,
        args.command is not None,
    ]
    if sum(active_top_level_modes) == 0:
        parser.error("Choose one scenario: --start_parser, --service, or test ...")
    if sum(active_top_level_modes) > 1:
        parser.error("Use only one top-level scenario at a time")

    if args.command == "test" and args.data_test == "downloaded-from-btc-data":
        if args.blocks_count is None:
            parser.error("blocks_count is required for downloaded-from-btc-data")
        if args.blocks_count <= 0:
            parser.error("blocks_count must be greater than 0")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified entrypoint for trade_app", epilog=EPILOG, formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("-p", "--start_parser", action="store_true", help="Старт парсера блокчейна")
    parser.add_argument(
        "-s",
        "--service",
        choices=["move_txs", "return_few_tx_wallets", "move_txs_back"],
        help="Сервисные функции",
    )
    
    scenario_subparsers = parser.add_subparsers(dest="command")

    # парсеры для запуска тестов
    test_parser = scenario_subparsers.add_parser(
        "test",
        help="Запуск тестовых сценариев",
    )

    test_subparsers = test_parser.add_subparsers(
        dest="data_test",
        required=True,
        title="available tests",
    )
    downloaded_btc_parser = test_subparsers.add_parser(
        "downloaded-from-btc-data",
        help="Сравнение SQL-данных с реконструкцией из BTC RPC",
    )
    downloaded_btc_parser.add_argument(
        "blocks_count",
        type=int,
        help="Сколько случайных блоков проверить",
    )
    downloaded_btc_parser.add_argument(
        "seed",
        type=int,
        nargs="?",
        help="Опциональный seed для воспроизводимой выборки",
    )

    # TODO(iteration_05_end): вернуть в новый CLI запуск остальных больших тестов
    # (`flask`, `main_pipeline`, `param_grid`, `converge_elasticnet`, `right_now_test`)
    # после отдельного разбора их структуры и аргументов.
    # test_parser.add_argument("-t", "--test", choices=["flask", "main_pipeline", "param_grid", "converge_elasticnet", "right_now_test"], help="Тестирование")

    args = parser.parse_args(argv)
    validate_cli_args(parser, args)

    return args

if __name__ == "__main__":

    args = parse_args()
    # print(args)

    tracker = RunTracker(args)
    id_ = tracker.id
    app_logger_module.setup_logging(id_)
    logger = logging.getLogger("app")
    logger.warning(f"Старт main.py, прогон № {id_}")
    app_logger_module.log_tracker_run_event(tracker, "run_started")

    try:
        if args.start_parser:
            import main_functions as mf

            warn_data_table_indexes_for_scenario("start_parser")
            mf.start_btc_core_monitor_and_parser()
            while True:
                time.sleep(1)
        
        if args.service == "move_txs":
            from modules.sql_funcs.moving_txs import moving_txs

            stage_data = tracker.start_stage("service.move_txs")
            app_logger_module.log_tracker_stage_started(tracker, stage_data)
            moving_txs()
            stage_data = tracker.finish_stage('success', details="move_txs finished")
            app_logger_module.log_tracker_stage_finished(tracker, stage_data)
            tracker.finish_run('success')
            app_logger_module.log_tracker_run_event(tracker, "run_finished")
            raise SystemExit(0)

        if args.service == "return_few_tx_wallets":
            from modules.sql_funcs.moving_txs import return_few_tx_wallets_to_data_table
            from settings.paths import BLOCKS_SQL_DATA

            stage_data = tracker.start_stage("service.return_few_tx_wallets")
            app_logger_module.log_tracker_stage_started(tracker, stage_data)
            warn_data_table_indexes_for_scenario("service.return_few_tx_wallets")
            return_few_tx_wallets_to_data_table(BLOCKS_SQL_DATA)
            stage_data = tracker.finish_stage('success', details="return_few_tx_wallets finished")
            app_logger_module.log_tracker_stage_finished(tracker, stage_data)
            tracker.finish_run('success')
            app_logger_module.log_tracker_run_event(tracker, "run_finished")
            raise SystemExit(0)

        if args.service == "move_txs_back":
            from modules.sql_funcs.moving_txs import move_txs_back

            stage_data = tracker.start_stage("service.move_txs_back")
            app_logger_module.log_tracker_stage_started(tracker, stage_data)
            move_txs_back()
            stage_data = tracker.finish_stage('success', details="move_txs_back finished")
            app_logger_module.log_tracker_stage_finished(tracker, stage_data)
            tracker.finish_run('success')
            app_logger_module.log_tracker_run_event(tracker, "run_finished")
            raise SystemExit(0)

        if args.command == "test":
            if args.data_test == "downloaded-from-btc-data":
                import main_functions as mf

                warn_data_table_indexes_for_scenario("integration_live.downloaded_from_btc_data")
                mf.run_downloaded_from_btc_data_test_scenario(
                    blocks_count=args.blocks_count,
                    seed=args.seed,
                )
                raise SystemExit(0)
            # TODO(iteration_05_end): сюда перенесем остальные большие тесты
        
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
        
        elif args.test == "right_now_test":
            import main_functions as mf
            mf.run_parser_now_and_wait()
            if tracker.status == 'running':
                tracker.finish_run('success')
                app_logger_module.log_tracker_run_event(tracker, "run_finished")
            raise SystemExit(0)

    except KeyboardInterrupt as e:
        if tracker.current_stage is not None:
            stage_data = tracker.finish_stage('interrupted', details=str(e))
            app_logger_module.log_tracker_stage_finished(tracker, stage_data)
        tracker.finish_run('interrupted', e)
        app_logger_module.log_tracker_run_event(tracker, "run_finished")
        raise

    except Exception as e:
        if tracker.current_stage is not None:
            stage_data = tracker.finish_stage('error', details=str(e))
            app_logger_module.log_tracker_stage_finished(tracker, stage_data)
        tracker.finish_run('error', e)
        app_logger_module.log_tracker_run_event(tracker, "run_finished", level=logging.ERROR)
        raise
    finally:
        app_logger_module.stop_logging()








