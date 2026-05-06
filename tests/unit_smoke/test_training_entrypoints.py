from modules.teach_and_update_models import training_entrypoints


def test_train_new_model_from_json_records_and_passes_collector(monkeypatch):
    metadata_updates = []
    teach_calls = []

    monkeypatch.setattr(training_entrypoints, "normalize_new_model_json_files", lambda: None)
    monkeypatch.setattr(
        training_entrypoints,
        "check_for_new_models",
        lambda: (
            "json",
            "ElasticNet",
            {"model": {"type": "ElasticNet"}},
            "model.json",
        ),
    )
    monkeypatch.setattr(training_entrypoints, "get_current_run_tracker", lambda: object())
    monkeypatch.setattr(
        training_entrypoints,
        "update_runtime_metadata",
        lambda tracker, **updates: metadata_updates.append(updates),
    )
    monkeypatch.setattr(
        training_entrypoints,
        "summarize_model_metadata",
        lambda *args: {"type": "ElasticNet"},
    )
    monkeypatch.setattr(
        training_entrypoints,
        "teach_model",
        lambda *args, **kwargs: teach_calls.append((args, kwargs)),
    )

    training_entrypoints.train_new_model_from_json(
        TEACHING_TEST=0,
        collector_name="wallet-stats",
    )

    assert metadata_updates == [
        {
            "collector": {"name": "wallet-stats"},
            "model_params": {"type": "ElasticNet"},
        }
    ]
    assert teach_calls[0][1]["collector_name"] == "wallet-stats"
