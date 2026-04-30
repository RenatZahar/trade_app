import json
import os

from modules.logger.experiment_metadata import summarize_model_metadata
from modules.logger.run_tracker import get_current_run_tracker
from modules.logger.runtime_bootstrap import update_runtime_metadata
from modules.teach_and_update_models.orchestrator import (
    teach_model,
    teaching_with_param_grid_orchestrator,
)
from modules.teach_and_update_models.service_funcs import check_for_new_models
from settings.paths import NEW_MODELS_PATH


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


def train_new_model_from_json(TEACHING_TEST, seed=None):
    normalize_new_model_json_files()
    model_type_data, model_type, model_info, model_dir_file = check_for_new_models()
    update_runtime_metadata(
        get_current_run_tracker(),
        model_params=summarize_model_metadata(
            model_type_data,
            model_type,
            model_info,
            model_dir_file,
        ),
    )
    teach_model(model_type_data, model_type, model_info, model_dir_file, TEACHING_TEST, seed=seed)


def run_param_grid(TEACHING_TEST, seed=None):
    teaching_with_param_grid_orchestrator(TEACHING_TEST, seed=seed)
