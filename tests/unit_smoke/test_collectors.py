import pytest

from modules.teach_and_update_models import collectors


def test_collect_correlation_training_data_legacy_delegates_to_current_collector(monkeypatch):
    calls = []

    def fake_get_corelation_by_tmsp_df(
        test,
        filter_params,
        correlation_type,
        tmps,
        chunk_size,
        seed=None,
    ):
        calls.append((test, filter_params, correlation_type, tmps, chunk_size, seed))
        return "train_df", "profit_df"

    monkeypatch.setattr(
        collectors.do,
        "get_corelation_by_tmsp_df",
        fake_get_corelation_by_tmsp_df,
    )

    result = collectors.collect_correlation_training_data(
        "legacy",
        collectors.CollectorRequest(
            test_fraction=0,
            filter_params={"correlation_threshold": 0.3},
            correlation_type="basic",
            time_window={"teaching_start_tmsp": 1},
            chunk_size=150,
            seed=13,
        ),
    )

    assert result.train_df == "train_df"
    assert result.profit_test_df == "profit_df"
    assert result.metadata == {
        "collector": "legacy",
        "source": "data_operations.get_corelation_by_tmsp_df",
    }
    assert calls == [
        (
            0,
            {"correlation_threshold": 0.3},
            "basic",
            {"teaching_start_tmsp": 1},
            150,
            13,
        )
    ]


def test_collect_correlation_training_data_defaults_to_legacy(monkeypatch):
    monkeypatch.setattr(
        collectors.do,
        "get_corelation_by_tmsp_df",
        lambda *args, **kwargs: ("train_df", "profit_df"),
    )

    assert collectors.collect_correlation_training_data(
        None,
        collectors.CollectorRequest(
            test_fraction=0,
            filter_params={},
            correlation_type="basic",
            time_window={},
            chunk_size=150,
        ),
    ).train_df == "train_df"


def test_collect_correlation_training_data_wallet_stats_is_explicit_stub():
    with pytest.raises(NotImplementedError, match="wallet-stats is not implemented"):
        collectors.collect_correlation_training_data(
            "wallet-stats",
            collectors.CollectorRequest(
                test_fraction=0,
                filter_params={},
                correlation_type="basic",
                time_window={},
                chunk_size=150,
            ),
        )


def test_collect_correlation_training_data_rejects_unknown_collector():
    with pytest.raises(ValueError, match="Unknown main pipeline collector"):
        collectors.collect_correlation_training_data(
            "unknown",
            collectors.CollectorRequest(
                test_fraction=0,
                filter_params={},
                correlation_type="basic",
                time_window={},
                chunk_size=150,
            ),
        )
