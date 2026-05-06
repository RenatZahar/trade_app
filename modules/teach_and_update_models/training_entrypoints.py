"""Public training runtime entrypoints.

Responsibility:
- expose the training subsystem functions called by `runtime_scenarios.py`;
- load/normalize active model configuration files and attach run metadata;
- delegate pipeline execution to `orchestrator.py`.

Non-responsibility:
- do not implement collector-specific data collection here;
- do not own train/evaluate/save stage sequencing;
- do not keep low-level dataframe, SQL, or Dask transformations here.
"""

import json
import os

from modules.logger.experiment_metadata import summarize_model_metadata
from modules.logger.run_tracker import get_current_run_tracker
from modules.logger.runtime_bootstrap import update_runtime_metadata
from modules.teach_and_update_models.collectors import DEFAULT_COLLECTOR
from modules.teach_and_update_models.orchestrator import (
    teach_model,
    teaching_with_param_grid_orchestrator,
)
from settings.paths import NEW_MODELS_PATH


def get_model_type(model_info):
    return model_info["model"]["type"]


def check_for_new_models():
    if not NEW_MODELS_PATH.exists():
        raise FileNotFoundError(f"Директория с новыми моделями не найдена: {NEW_MODELS_PATH}")

    files = [f for f in NEW_MODELS_PATH.iterdir() if f.is_file()]
    if not files:
        raise FileNotFoundError(f"В директории {NEW_MODELS_PATH} нет файлов моделей для обучения.")

    for file in files:
        if "example" in file.name:
            continue
        full_dir_file = os.path.join(NEW_MODELS_PATH, file)
        if file.suffix == ".json":
            with open(full_dir_file, "r", encoding="utf-8") as file:
                model_info = json.load(file)
                model_type = get_model_type(model_info)
            return "json", model_type, model_info, full_dir_file
        if file.suffix == ".pkl":
            return "pkl", None, None, None

    raise RuntimeError(f"В директории {NEW_MODELS_PATH} не найден поддерживаемый файл модели.")


def normalize_new_model_json_files():
    files = [f for f in NEW_MODELS_PATH.iterdir() if f.is_file()]

    for file in files:
        if "example" in file.name:
            continue
        full_dir_file = os.path.join(NEW_MODELS_PATH, file)
        if file.suffix == ".json":
            with open(full_dir_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            with open(full_dir_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)


def train_new_model_from_json(TEACHING_TEST, seed=None, collector_name=DEFAULT_COLLECTOR):
    normalize_new_model_json_files()
    model_type_data, model_type, model_info, model_dir_file = check_for_new_models()
    update_runtime_metadata(
        get_current_run_tracker(),
        collector={"name": collector_name},
        model_params=summarize_model_metadata(
            model_type_data,
            model_type,
            model_info,
            model_dir_file,
        ),
    )
    teach_model(
        model_type_data,
        model_type,
        model_info,
        model_dir_file,
        TEACHING_TEST,
        seed=seed,
        collector_name=collector_name,
    )


def run_param_grid(TEACHING_TEST, seed=None):
    teaching_with_param_grid_orchestrator(TEACHING_TEST, seed=seed)
