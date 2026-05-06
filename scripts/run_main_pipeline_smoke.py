import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
# почему не в тест его? пригодится, на будущие изменения пайплайна. предусмотреть логи по взаимодействию функций внутри пайплайна

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NEW_MODELS_DIR = PROJECT_ROOT / "data" / "models" / "new_models" #перенести ссылку в settings


def find_active_model_json(model_json: Path | None = None) -> Path:
    if model_json is not None:
        resolved = model_json.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Model JSON does not exist: {resolved}")
        return resolved

    candidates = sorted(
        path for path in NEW_MODELS_DIR.glob("*.json")
        if "example" not in path.name.lower()
    )
    if not candidates:
        raise RuntimeError(
            "Expected at least one active model JSON in "
            f"{NEW_MODELS_DIR}, found 0."
        )
    return candidates[0]


def build_smoke_model_config(source_config: dict, days: int) -> dict:
    if days <= 0:
        raise ValueError("days must be greater than 0")

    config = json.loads(json.dumps(source_config))
    time_params = config["model"]["time_params"]
    time_params.update(
        {
            "iterations": 1,
            "training_data_duration_months": 0,
            "model_relevance_period_months": 0,
            "profit_test_months": 0,
            "training_data_duration_days": days,
            "model_relevance_period_days": 0,
            "profit_test_days": days,
            "time_to_get_cmlt_day": max(1, min(days, time_params.get("time_to_get_cmlt_day", 1))),
        }
    )
    comment = config["model"].get("comment", "")
    config["model"]["comment"] = f"{comment} [smoke_days={days}]".strip()
    return config


def run_smoke(model_json: Path, days: int) -> int:
    original_content = model_json.read_text(encoding="utf-8")
    backup_path = model_json.with_name(
        f"{model_json.stem}.smoke-backup-{datetime.now():%Y%m%d_%H%M%S}{model_json.suffix}"
    )
    backup_path.write_text(original_content, encoding="utf-8")

    try:
        source_config = json.loads(original_content)
        smoke_config = build_smoke_model_config(source_config, days=days)
        model_json.write_text(
            json.dumps(smoke_config, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, "main.py", "main-pipeline"],
            cwd=PROJECT_ROOT,
        )
        return result.returncode
    finally:
        model_json.write_text(original_content, encoding="utf-8")
        if backup_path.exists():
            backup_path.unlink()
 

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run main-pipeline with temporary short model time windows."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Short training/profit-test window size in days.",
    )
    parser.add_argument(
        "--model-json",
        type=Path,
        help="Active model JSON to temporarily override. Defaults to the only non-example JSON in new_models.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    model_json = find_active_model_json(args.model_json)
    return run_smoke(model_json=model_json, days=args.days)


if __name__ == "__main__":
    raise SystemExit(main())
