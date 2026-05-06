import json
from pathlib import Path

import pytest

from scripts.run_main_pipeline_smoke import (
    build_smoke_model_config,
    find_active_model_json,
)


def _source_model_config():
    return {
        "model": {
            "type": "ElasticNet",
            "model_param": {
                "alpha": 0.1,
                "l1_ratio": 0.5,
                "decision_threshold": 0.01,
            },
            "time_params": {
                "iterations": 3,
                "training_data_duration_months": 12,
                "model_relevance_period_months": 2,
                "profit_test_months": 2,
                "time_to_get_cmlt_day": 14,
            },
            "filters": {
                "txs_count_of_wallets": 5,
                "correlation_threshold": 0.2,
            },
            "correlation_params": {
                "correlation_type": "basic",
            },
            "comment": "source model",
        }
    }


def test_build_smoke_model_config_uses_short_day_windows_without_mutating_source():
    source_config = _source_model_config()

    smoke_config = build_smoke_model_config(source_config, days=7)

    assert source_config["model"]["time_params"]["training_data_duration_months"] == 12
    assert "training_data_duration_days" not in source_config["model"]["time_params"]
    assert smoke_config["model"]["time_params"] == {
        "iterations": 1,
        "training_data_duration_months": 0,
        "model_relevance_period_months": 0,
        "profit_test_months": 0,
        "time_to_get_cmlt_day": 7,
        "training_data_duration_days": 7,
        "model_relevance_period_days": 0,
        "profit_test_days": 7,
    }
    assert "smoke_days=7" in smoke_config["model"]["comment"]


def test_build_smoke_model_config_rejects_non_positive_days():
    with pytest.raises(ValueError, match="days must be greater than 0"):
        build_smoke_model_config(_source_model_config(), days=0)


def test_find_active_model_json_accepts_explicit_existing_path(tmp_path):
    model_path = tmp_path / "model.json"
    model_path.write_text(json.dumps(_source_model_config()), encoding="utf-8")

    assert find_active_model_json(model_path) == model_path.resolve()


def test_find_active_model_json_rejects_missing_explicit_path(tmp_path):
    missing_path = Path(tmp_path / "missing.json")

    with pytest.raises(FileNotFoundError):
        find_active_model_json(missing_path)


def test_find_active_model_json_uses_first_active_json_when_several_exist(tmp_path, monkeypatch):
    first_model = tmp_path / "a_model.json"
    second_model = tmp_path / "b_model.json"
    example_model = tmp_path / "example_model.json"
    first_model.write_text(json.dumps(_source_model_config()), encoding="utf-8")
    second_model.write_text(json.dumps(_source_model_config()), encoding="utf-8")
    example_model.write_text(json.dumps(_source_model_config()), encoding="utf-8")

    import scripts.run_main_pipeline_smoke as smoke_script

    monkeypatch.setattr(smoke_script, "NEW_MODELS_DIR", tmp_path)

    assert find_active_model_json() == first_model
