"""Main entrypoint for local service orchestration.

Operational notes and backlog for this file were moved to:
- docs/main_notes.md
"""

from cli_args import parse_args
import modules.logger.logger as app_logger_module
from modules.logger.runtime_bootstrap import (
    finish_runtime_error,
    finish_runtime_interrupted,
    finish_runtime_success,
    start_runtime_logging,
)


if __name__ == "__main__":
    args = parse_args()
    tracker, logger = start_runtime_logging(args)

    try:
        if args.command == "main-pipeline":
            import runtime_scenarios as scenarios

            scenarios.prepare_training_data_and_train_new_model(
                collector_name=args.collector
            )
            finish_runtime_success(tracker)
            raise SystemExit(0)

        if args.command == "param-grid":
            import runtime_scenarios as scenarios

            scenarios.run_param_grid_scenario(test_fraction=args.test_fraction, seed=args.seed)
            finish_runtime_success(tracker)
            raise SystemExit(0)
        
        if args.start_parser:
            import runtime_scenarios as scenarios

            scenarios.run_parser_monitor_scenario(
                tx_cache_lines=args.parser_tx_cache_lines,
                hash_cache_lines=args.parser_hash_cache_lines,
            )
        
        if args.command == "test":
            if args.data_test == "downloaded-from-btc-data":
                import runtime_scenarios as scenarios

                scenarios.run_downloaded_from_btc_data_scenario(
                    blocks_count=args.blocks_count,
                    seed=args.seed,
                    blocks=args.blocks,
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








