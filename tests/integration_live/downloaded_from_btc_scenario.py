import json
import logging

from modules.logger import logger as app_logger_module
from modules.logger.run_tracker import get_current_run_tracker
from tests.integration_live.test_downloaded_from_btc_data import run_downloaded_from_btc_data_test


logger = logging.getLogger("app")


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
        stage_data = tracker.finish_stage("error", details=str(e))
        app_logger_module.log_tracker_stage_finished(tracker, stage_data)
        raise

    if not isinstance(test_summary, dict):
        raise RuntimeError("Downloaded-from-BTC integration test must return a summary dict.")

    details = format_downloaded_from_btc_stage_details(test_summary)
    stage_data = tracker.finish_stage("success", details=details)
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
    tracker.finish_run("success")
    app_logger_module.log_tracker_run_event(tracker, "run_finished")
    return test_summary
