import os
import importlib.util

import pandas as pd
import pytest


def _skip_if_legacy_data_operations_is_missing():
    if importlib.util.find_spec("modules.teach_and_update_models.data_operations") is None:
        pytest.skip(
            "legacy modules.teach_and_update_models.data_operations is not tracked in git"
        )


def test_get_tmsps_data_of_model_builds_required_pipeline_windows(monkeypatch):
    _skip_if_legacy_data_operations_is_missing()
    cwd = os.getcwd()
    from modules.teach_and_update_models import service_funcs as sf
    os.chdir(cwd)

    monkeypatch.setattr(sf.do, "get_last_block_info", lambda: (100, 10_000_000))
    time_params = {
        "iterations": 1,
        "model_relevance_period_months": 0,
        "profit_test_months": 1,
        "training_data_duration_months": 2,
        "time_to_get_cmlt_day": 7,
    }

    tmsps_data = sf.get_tmsps_data_of_model(time_params)

    first_iteration = tmsps_data[1]
    assert "profit_test_start_tmsp" in first_iteration
    assert "profit_test_end_tmsp" in first_iteration
    assert "teaching_start_tmsp" in first_iteration
    assert "teaching_end_tmsp" in first_iteration
    assert "cmlt_start_tmsp" in first_iteration
    assert "cmlt_end_tmsp" in first_iteration
    assert first_iteration["cmlt_end_tmsp"] < first_iteration["teaching_start_tmsp"]
    assert first_iteration["teaching_end_tmsp"] < first_iteration["profit_test_start_tmsp"]


def test_normalize_amount_keeps_buy_and_sell_amounts_in_separate_feature_columns():
    _skip_if_legacy_data_operations_is_missing()
    cwd = os.getcwd()
    from modules.teach_and_update_models import data_operations as do
    os.chdir(cwd)

    txs = pd.DataFrame(
        [
            {"Wallet_id": "wallet_a", "Amount": 1.0},
            {"Wallet_id": "wallet_a", "Amount": 2.0},
            {"Wallet_id": "wallet_a", "Amount": -1.0},
            {"Wallet_id": "wallet_a", "Amount": -3.0},
        ]
    )

    normalized_txs = do.normalize_amount(txs)

    assert "Normalized_buy_amount" in normalized_txs.columns
    assert "Normalized_sell_amount" in normalized_txs.columns

    buy_rows = normalized_txs.loc[normalized_txs["Amount"] > 0]
    sell_rows = normalized_txs.loc[normalized_txs["Amount"] < 0]

    assert (buy_rows["Normalized_sell_amount"] == 0).all()
    assert (buy_rows["Normalized_buy_amount"] >= 0).all()
    assert (sell_rows["Normalized_buy_amount"] == 0).all()
    assert (sell_rows["Normalized_sell_amount"] <= 0).all()
