import importlib.util
import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def test_core_runtime_packages_import():
    import dask
    import distributed
    import pyarrow
    import scipy
    import sklearn

    assert dask.__version__
    assert distributed.__version__
    assert pd.__version__
    assert pyarrow.__version__
    assert np.__version__
    assert scipy.__version__
    assert sklearn.__version__


def test_project_uses_version_compatible_dask_dataframe_backend():
    from settings.dask import (
        configure_dask_dataframe_backend,
        dask_dataframe_query_planning_setting,
    )

    configure_dask_dataframe_backend()

    import dask
    import dask.dataframe as dd

    expected_query_planning = dask_dataframe_query_planning_setting()
    assert dask.config.get("dataframe.query-planning") is expected_query_planning
    if expected_query_planning:
        assert dd.DataFrame.__module__ == "dask.dataframe.dask_expr._collection"
    else:
        assert dd.DataFrame.__module__ == "dask.dataframe.core"
        assert importlib.util.find_spec("dask_expr") is None


def test_tracked_runtime_modules_do_not_top_level_import_private_data_operations():
    repo_root = Path(__file__).resolve().parents[2]
    module_paths = [
        "modules/teach_and_update_models/collectors.py",
        "modules/teach_and_update_models/model_classes.py",
        "modules/teach_and_update_models/orchestrator.py",
        "modules/teach_and_update_models/service_funcs.py",
        "modules/teach_and_update_models/wallet_stats_operations.py",
    ]

    offenders = []
    for module_path in module_paths:
        tree = ast.parse((repo_root / module_path).read_text(encoding="utf-8"))
        for node in tree.body:
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is None
                and any(alias.name == "data_operations" for alias in node.names)
            ):
                offenders.append(module_path)

    assert offenders == []


def test_dask_parquet_merge_asof_groupby_smoke(tmp_path):
    from settings.dask import configure_dask_dataframe_backend

    configure_dask_dataframe_backend()

    import dask.dataframe as dd

    txs = pd.DataFrame(
        {
            "Block_time": [100, 160, 220, 400],
            "Wallet_id": ["a", "a", "b", "b"],
            "Weighted_sell_correlation": [1.0, 2.0, 3.0, 4.0],
            "Weighted_buy_correlation": [0.5, 1.0, 1.5, 2.0],
        }
    ).sort_values("Block_time")
    intervals = pd.DataFrame({"Timestamp": [120, 240, 420]}).sort_values("Timestamp")

    parquet_dir = tmp_path / "txs.parquet"
    dd.from_pandas(txs, npartitions=2).to_parquet(parquet_dir, engine="pyarrow")
    txs_ddf = dd.read_parquet(parquet_dir, engine="pyarrow").sort_values("Block_time")
    intervals_ddf = dd.from_pandas(intervals, npartitions=1)

    merged = dd.merge_asof(
        txs_ddf,
        intervals_ddf,
        left_on="Block_time",
        right_on="Timestamp",
        direction="nearest",
        tolerance=60,
    )
    merged["Nearest_tmps_from_learning_data"] = merged["Timestamp"]
    grouped = merged.groupby("Nearest_tmps_from_learning_data").agg(
        {
            "Weighted_sell_correlation": "sum",
            "Weighted_buy_correlation": "sum",
        }
    )

    result = grouped.compute().sort_index()

    assert result.index.tolist() == [120, 240, 420]
    assert result["Weighted_sell_correlation"].tolist() == [3.0, 3.0, 4.0]
    assert result["Weighted_buy_correlation"].tolist() == [1.5, 1.5, 2.0]


def test_pandas_resample_and_groupby_apply_contract():
    source = pd.DataFrame(
        {
            "Wallet_id": ["a", "a", "b", "b"],
            "ts": pd.to_datetime(
                ["2026-01-01 00:00", "2026-01-01 00:01", "2026-01-01 00:00", "2026-01-01 00:01"]
            ),
            "value": [1.0, 3.0, 2.0, 4.0],
        }
    )

    resampled = source.set_index("ts")["value"].resample("1min").mean()
    grouped = (
        source.groupby("Wallet_id")
        .apply(lambda group: group.assign(centered=group["value"] - group["value"].mean()), include_groups=False)
        .reset_index(level=0)
        .reset_index(drop=True)
    )

    assert resampled.tolist() == [1.5, 3.5]
    assert grouped.groupby("Wallet_id")["centered"].sum().round(10).tolist() == [0.0, 0.0]


def test_scipy_and_sklearn_pipeline_smoke(tmp_path):
    from joblib import dump, load
    from scipy.signal import find_peaks
    from sklearn.linear_model import ElasticNet
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    peaks, _ = find_peaks(np.array([1.0, 3.0, 1.0, 2.0, 1.0]))
    assert peaks.tolist() == [1, 3]

    x = pd.DataFrame({"a": [0.0, 1.0, 2.0, 3.0], "b": [3.0, 2.0, 1.0, 0.0]})
    y = pd.Series([0.0, 1.0, 1.0, 0.0])
    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("regressor", ElasticNet(alpha=0.1, l1_ratio=0.5, max_iter=10000)),
        ]
    )
    model.fit(x, y)

    model_path = tmp_path / "model.joblib"
    dump(model, model_path)
    loaded_model = load(model_path)
    predictions = loaded_model.predict(x)

    assert predictions.shape == (4,)
    assert np.isfinite(predictions).all()
