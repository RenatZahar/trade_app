import os

import pandas as pd
import pytest
from sklearn.pipeline import Pipeline


def _general_model():
    cwd = os.getcwd()
    from modules.teach_and_update_models.model_classes import GeneralModel
    os.chdir(cwd)

    return GeneralModel(
        {
            "model": {
                "type": "ElasticNet",
                "model_param": {},
                "time_params": {},
                "filters": {},
                "correlation_params": {},
            }
        }
    )


def _general_model_with_params(model_param):
    cwd = os.getcwd()
    from modules.teach_and_update_models.model_classes import GeneralModel
    os.chdir(cwd)

    return GeneralModel(
        {
            "model": {
                "type": "ElasticNet",
                "model_param": model_param,
                "time_params": {},
                "filters": {},
                "correlation_params": {},
            }
        }
    )


def test_prepare_feature_frame_drops_non_feature_columns_and_preserves_order():
    model = _general_model()
    data = pd.DataFrame(
        {
            "index": [10],
            "feature_b": [2.0],
            "Action": [1],
            "Price": [100.0],
            "feature_a": [1.0],
            "Predicted_Action": [0],
        }
    )

    feature_frame = model.prepare_feature_frame(data)

    assert feature_frame.columns.tolist() == ["feature_b", "feature_a"]


def test_prepare_feature_frame_restores_train_order_and_fails_on_missing_features():
    model = _general_model()
    train_feature_columns = ["feature_b", "feature_a"]
    prediction_data = pd.DataFrame(
        {
            "feature_a": [1.0],
            "feature_b": [2.0],
            "index": [10],
            "extra_feature": [99.0],
        }
    )

    feature_frame = model.prepare_feature_frame(prediction_data, train_feature_columns)

    assert feature_frame.columns.tolist() == train_feature_columns

    with pytest.raises(ValueError, match="Missing features"):
        model.prepare_feature_frame(
            pd.DataFrame({"feature_a": [1.0]}),
            train_feature_columns,
        )


def test_model_parameters_normalize_legacy_threshold_to_decision_threshold():
    model = _general_model_with_params(
        {"alpha": 0.1, "l1_ratio": 0.5, "threshold": 0.2}
    )

    assert model.model_parameters == {
        "alpha": 0.1,
        "l1_ratio": 0.5,
        "decision_threshold": 0.2,
    }


def test_model_parameters_reject_conflicting_threshold_names():
    with pytest.raises(ValueError, match="Conflicting threshold"):
        _general_model_with_params(
            {
                "alpha": 0.1,
                "l1_ratio": 0.5,
                "threshold": 0.2,
                "decision_threshold": 0.3,
            }
        )


def test_elasticnet_training_stores_scaler_aware_pipeline(monkeypatch):
    cwd = os.getcwd()
    from modules.teach_and_update_models.model_classes import ElasticNetModel
    os.chdir(cwd)

    monkeypatch.setattr(pd.DataFrame, "to_parquet", lambda self, *args, **kwargs: None)

    model = ElasticNetModel(
        {
            "model": {
                "type": "ElasticNet",
                "model_param": {
                    "alpha": 0.1,
                    "l1_ratio": 0.5,
                    "decision_threshold": 0.01,
                },
                "time_params": {},
                "filters": {},
                "correlation_params": {},
            }
        }
    )
    train_data = pd.DataFrame(
        {
            "index": [100, 101, 102, 103],
            "feature_a": [1.0, 2.0, 3.0, 4.0],
            "feature_b": [4.0, 3.0, 2.0, 1.0],
            "Action": [1, 0, -1, 1],
            "Price": [10.0, 11.0, 12.0, 13.0],
        }
    )
    profit_data = train_data.copy()

    model.train_model_specific(train_data, profit_data, seed=7)

    assert isinstance(model.model, Pipeline)
    assert list(model.model.named_steps) == ["scaler", "regressor"]
    assert model.model_feature_columns == ["feature_a", "feature_b"]
