from argparse import Namespace

from modules.logger import experiment_metadata as em


def test_build_experiment_metadata_collects_seed_args_and_runtime(monkeypatch):
    monkeypatch.setattr(em, "get_git_commit_hash", lambda: "abc123")
    monkeypatch.setattr(em, "get_package_version", lambda package_name: f"{package_name}-version")

    args = Namespace(command="test", data_test="downloaded-from-btc-data", seed=13)
    metadata = em.build_experiment_metadata(args)

    assert metadata["commit_hash"] == "abc123"
    assert metadata["seed"] == 13
    assert metadata["args"]["data_test"] == "downloaded-from-btc-data"
    assert metadata["versions"]["pandas"] == "pandas-version"
    assert metadata["versions"]["dask"] == "dask-version"
    assert metadata["versions"]["sklearn"] == "scikit-learn-version"
    assert metadata["runtime"]["blocks_sql_data"]
    assert "txs_moved" in metadata["sql_state"]
    assert metadata["parser_cache"]["max_lines_in_tx_cache"] >= 0
    assert metadata["parser_cache"]["max_lines_in_hash_cache"] >= 0


def test_build_experiment_metadata_records_parser_cache_overrides(monkeypatch):
    monkeypatch.setattr(em, "get_git_commit_hash", lambda: "abc123")
    monkeypatch.setattr(em, "get_package_version", lambda package_name: None)

    metadata = em.build_experiment_metadata(
        Namespace(seed=None, parser_tx_cache_lines=0, parser_hash_cache_lines=0)
    )

    assert metadata["parser_cache"] == {
        "max_lines_in_tx_cache": 0,
        "max_lines_in_hash_cache": 0,
        "tx_cache_enabled": False,
        "blocks_hash_cache_enabled": False,
        "tx_cache_override": 0,
        "blocks_hash_cache_override": 0,
    }


def test_build_experiment_metadata_explicit_seed_overrides_args(monkeypatch):
    monkeypatch.setattr(em, "get_git_commit_hash", lambda: "abc123")
    monkeypatch.setattr(em, "get_package_version", lambda package_name: None)

    metadata = em.build_experiment_metadata(Namespace(seed=1), seed=2)

    assert metadata["seed"] == 2


def test_summarize_model_metadata_keeps_reproducible_model_params():
    model_info = {
        "model": {
            "type": "ElasticNet",
            "model_param": {"alpha": 0.1},
            "time_params": {"iterations": 1},
            "filters": {"min_amount": 0.01},
            "correlation_params": {"correlation_type": "basic"},
            "comment": "test model",
        }
    }

    metadata = em.summarize_model_metadata("json", "ElasticNet", model_info, "model.json")

    assert metadata["source_type"] == "json"
    assert metadata["source_file"] == "model.json"
    assert metadata["type"] == "ElasticNet"
    assert metadata["model_param"] == {"alpha": 0.1}
    assert metadata["time_params"] == {"iterations": 1}
    assert metadata["filters"] == {"min_amount": 0.01}
    assert metadata["correlation_params"] == {"correlation_type": "basic"}


def test_summarize_grid_metadata_limits_preview_and_keeps_count():
    grid_params = [{"model": {"model_param": {"alpha": value}}} for value in range(7)]

    metadata = em.summarize_grid_metadata({"iterations": 1}, grid_params, preview_limit=3)

    assert metadata["time_params"] == {"iterations": 1}
    assert metadata["combinations_count"] == 7
    assert metadata["preview_limit"] == 3
    assert metadata["truncated"] is True
    assert metadata["combinations_preview"] == grid_params[:3]
