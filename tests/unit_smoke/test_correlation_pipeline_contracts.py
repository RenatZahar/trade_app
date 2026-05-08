import os
import importlib.util
import inspect
import sys
import types
from pathlib import Path

import pandas as pd
import pytest
# самому написать pytest с нуля! нихера не понимаю как самому это сделать. агент, как увидишь эту запись - поставь в итерацию по обучеиню этот пункт а запись удали

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

    fake_data_operations = types.ModuleType(
        "modules.teach_and_update_models.data_operations"
    )
    fake_data_operations.get_last_block_info = lambda: (100, 10_000_000)
    monkeypatch.setitem(
        sys.modules,
        "modules.teach_and_update_models.data_operations",
        fake_data_operations,
    )
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


def test_get_tmsps_data_of_model_accepts_smoke_day_windows(monkeypatch):
    _skip_if_legacy_data_operations_is_missing()
    cwd = os.getcwd()
    from modules.teach_and_update_models import service_funcs as sf
    os.chdir(cwd)

    fake_data_operations = types.ModuleType(
        "modules.teach_and_update_models.data_operations"
    )
    fake_data_operations.get_last_block_info = lambda: (100, 10_000_000)
    monkeypatch.setitem(
        sys.modules,
        "modules.teach_and_update_models.data_operations",
        fake_data_operations,
    )
    time_params = {
        "iterations": 1,
        "model_relevance_period_months": 0,
        "profit_test_months": 0,
        "training_data_duration_months": 0,
        "model_relevance_period_days": 0,
        "profit_test_days": 7,
        "training_data_duration_days": 7,
        "time_to_get_cmlt_day": 1,
    }

    first_iteration = sf.get_tmsps_data_of_model(time_params)[1]

    assert first_iteration["profit_test_end_tmsp"] - first_iteration["profit_test_start_tmsp"] == 7 * 24 * 60 * 60
    assert first_iteration["teaching_end_tmsp"] - first_iteration["teaching_start_tmsp"] == 7 * 24 * 60 * 60
    assert first_iteration["cmlt_end_tmsp"] - first_iteration["cmlt_start_tmsp"] == 24 * 60 * 60


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


def test_filter_timestamp_window_includes_only_requested_boundaries():
    _skip_if_legacy_data_operations_is_missing()
    cwd = os.getcwd()
    from modules.teach_and_update_models import data_operations as do
    os.chdir(cwd)

    data = pd.DataFrame(
        {
            "Timestamp": [900, 1000, 1500, 2000, 2100],
            "value": ["before", "start", "inside", "end", "after"],
        }
    )

    filtered = do.filter_timestamp_window(data, "Timestamp", 1000, 2000)

    assert filtered["value"].tolist() == ["start", "inside", "end"]


def test_import_peak_intervals_uses_writeable_interval_arrays():
    _skip_if_legacy_data_operations_is_missing()
    cwd = os.getcwd()
    from modules.teach_and_update_models import data_operations as do
    os.chdir(cwd)

    txs = pd.DataFrame(
        {
            "Block_time": [100, 200, 1000],
            "Wallet_id": ["wallet_a", "wallet_b", "wallet_c"],
        }
    )
    peaks = pd.DataFrame(
        {
            "Timestamp": [200, 1000],
            "Buy": [0, 1],
            "Sell": [1, 0],
        }
    )

    marked_txs = do.import_peak_intervals(txs, peaks)

    assert marked_txs["in_sell_interval"].tolist() == [-1, -1, 0]
    assert marked_txs["in_buy_interval"].tolist() == [0, 0, 1]
    assert "in_sell_interval" not in txs.columns
    assert "in_buy_interval" not in txs.columns


def test_calculate_correlation_basic_drops_wallets_below_threshold():
    _skip_if_legacy_data_operations_is_missing()
    cwd = os.getcwd()
    from modules.teach_and_update_models import data_operations as do
    os.chdir(cwd)

    txs = pd.DataFrame(
        [
            {
                "Wallet_id": "wallet_good",
                "Amount": -1.0,
                "Normalized_sell_amount": -1.0,
                "Normalized_buy_amount": 0.0,
                "in_sell_interval": -1,
                "in_buy_interval": 0,
            },
            {
                "Wallet_id": "wallet_good",
                "Amount": 1.0,
                "Normalized_sell_amount": 0.0,
                "Normalized_buy_amount": 1.0,
                "in_sell_interval": 0,
                "in_buy_interval": 1,
            },
            {
                "Wallet_id": "wallet_good",
                "Amount": -2.0,
                "Normalized_sell_amount": -2.0,
                "Normalized_buy_amount": 0.0,
                "in_sell_interval": -1,
                "in_buy_interval": 0,
            },
            {
                "Wallet_id": "wallet_good",
                "Amount": 2.0,
                "Normalized_sell_amount": 0.0,
                "Normalized_buy_amount": 2.0,
                "in_sell_interval": 0,
                "in_buy_interval": 1,
            },
            {
                "Wallet_id": "wallet_bad",
                "Amount": 1.0,
                "Normalized_sell_amount": 0.0,
                "Normalized_buy_amount": 0.0,
                "in_sell_interval": 0,
                "in_buy_interval": 1,
            },
            {
                "Wallet_id": "wallet_bad",
                "Amount": -1.0,
                "Normalized_sell_amount": 0.0,
                "Normalized_buy_amount": 0.0,
                "in_sell_interval": -1,
                "in_buy_interval": 0,
            },
        ]
    )

    correlations = do.calculate_correlation_basic(txs, correlation_threshold=0.9)

    assert correlations["Wallet_id"].tolist() == ["wallet_good"]
    assert "0.0" not in correlations["Wallet_id"].tolist()


def test_price_line_window_contract_is_derived_from_price_peaks_settings():
    _skip_if_legacy_data_operations_is_missing()
    cwd = os.getcwd()
    from modules.teach_and_update_models import data_operations as do
    from settings.price_peaks import line_time_duration_min
    os.chdir(cwd)

    assert do.PRICE_LINE_DURATION_SEC == line_time_duration_min * 60
    assert do.PRICE_LINE_HALF_WINDOW_SEC == do.PRICE_LINE_DURATION_SEC / 2


def test_transform_btc_to_intervals_uses_price_line_duration_window():
    _skip_if_legacy_data_operations_is_missing()
    cwd = os.getcwd()
    from modules.teach_and_update_models import data_operations as do
    os.chdir(cwd)

    btc_rows = pd.DataFrame(
        {
            "Timestamp": [1000, 2000, 3000],
            "Buy": [0, 1, 0],
            "Sell": [1, 0, 0],
        }
    )

    intervals = do.transform_btc_to_intervals(btc_rows)

    assert intervals["Start"].tolist() == [
        1000 - do.PRICE_LINE_DURATION_SEC,
        2000 - do.PRICE_LINE_DURATION_SEC,
    ]
    assert intervals["End"].tolist() == [
        1000 + do.PRICE_LINE_DURATION_SEC,
        2000 + do.PRICE_LINE_DURATION_SEC,
    ]


def test_correlation_pipeline_passes_threshold_and_type_by_name():
    _skip_if_legacy_data_operations_is_missing()
    cwd = os.getcwd()
    from modules.teach_and_update_models import data_operations as do
    os.chdir(cwd)

    source = inspect.getsource(do.process_chunk)

    assert "correlation_threshold=correlation_threshold" in source
    assert "correlation_type=correlation_type" in source


def test_ensure_dask_dataframe_accepts_dask_dataframe_objects():
    _skip_if_legacy_data_operations_is_missing()
    cwd = os.getcwd()
    from modules.teach_and_update_models import data_operations as do
    from settings.dask import dask_dataframe_query_planning_setting
    os.chdir(cwd)

    ddf = do.dd.from_pandas(pd.DataFrame({"value": [1, 2]}), npartitions=1)

    expected_module = (
        "dask.dataframe.dask_expr._collection"
        if dask_dataframe_query_planning_setting()
        else "dask.dataframe.core"
    )
    assert do.dd.DataFrame.__module__ == expected_module
    assert do.is_dask_dataframe_like(ddf)
    assert do.ensure_dask_dataframe(ddf) is ddf


def test_requirements_lock_does_not_include_dask_expr():
    lock_path = Path(__file__).resolve().parents[2] / "requirements.lock.txt"
    lock_content = lock_path.read_text(encoding="utf-8")

    assert "dask-expr" not in lock_content


def test_ensure_dask_dataframe_accepts_dask_dataframe_like_objects():
    _skip_if_legacy_data_operations_is_missing()
    cwd = os.getcwd()
    from modules.teach_and_update_models import data_operations as do
    os.chdir(cwd)

    class LegacyDaskDataFrameLike:
        npartitions = 1

        def compute(self):
            return pd.DataFrame()

        def map_partitions(self):
            return self

    legacy_ddf = LegacyDaskDataFrameLike()

    assert do.is_dask_dataframe_like(legacy_ddf)
    assert do.ensure_dask_dataframe(legacy_ddf) is legacy_ddf


def test_reset_runtime_parquet_dir_only_clears_runtime_parquet_artifacts(tmp_path, monkeypatch):
    _skip_if_legacy_data_operations_is_missing()
    cwd = os.getcwd()
    from modules.teach_and_update_models import data_operations as do
    os.chdir(cwd)

    runtime_root = tmp_path / "runtime"
    target_dir = runtime_root / "chunks"
    target_dir.mkdir(parents=True)
    parquet_file = target_dir / "old.parquet"
    parquet_file.write_text("old", encoding="utf-8")
    parquet_dir = target_dir / "old_dir.parquet"
    parquet_dir.mkdir()
    (parquet_dir / "part.0.parquet").write_text("old", encoding="utf-8")
    keep_file = target_dir / "keep.txt"
    keep_file.write_text("keep", encoding="utf-8")

    monkeypatch.setattr(do, "dir_for_temp_files_of_module", str(runtime_root))

    do.reset_runtime_parquet_dir(target_dir)

    assert not parquet_file.exists()
    assert not parquet_dir.exists()
    assert keep_file.exists()

    with pytest.raises(ValueError, match="outside runtime temp dir"):
        do.reset_runtime_parquet_dir(tmp_path / "outside")


def test_reset_runtime_parquet_dir_accepts_explicit_runtime_root(tmp_path):
    _skip_if_legacy_data_operations_is_missing()
    cwd = os.getcwd()
    from modules.teach_and_update_models import data_operations as do
    os.chdir(cwd)

    runtime_root = tmp_path / "custom_runtime"
    target_dir = runtime_root / "checkpoint"
    target_dir.mkdir(parents=True)
    parquet_file = target_dir / "part.0.parquet"
    parquet_file.write_text("old", encoding="utf-8")

    do.reset_runtime_parquet_dir(target_dir, runtime_root)

    assert target_dir.exists()
    assert not parquet_file.exists()

    with pytest.raises(ValueError, match="outside runtime temp dir"):
        do.reset_runtime_parquet_dir(tmp_path / "outside", runtime_root)


def test_basic_correlation_pipeline_materializes_merge_asof_checkpoint():
    _skip_if_legacy_data_operations_is_missing()
    cwd = os.getcwd()
    from modules.teach_and_update_models import data_operations as do
    os.chdir(cwd)

    source = inspect.getsource(do.teach_n_test_data_with_basic_corrs)

    assert "3_merged_after_asof_checkpoint" in source
    assert "merged_after_asof_checkpoint_read_parquet" in source


def test_correlation_pipeline_avoids_nested_delayed_and_dask_len_empty_check():
    _skip_if_legacy_data_operations_is_missing()
    cwd = os.getcwd()
    from modules.teach_and_update_models import data_operations as do
    os.chdir(cwd)

    source = inspect.getsource(do.get_corelation_of_wallets_df_with_dask)

    assert "@delayed" not in source
    assert "len(all_txs_of_wallets_ddf)" not in source
    assert "successful_chunks" in source
