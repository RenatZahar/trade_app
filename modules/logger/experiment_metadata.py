import platform
import subprocess
from importlib import metadata

from settings.paths import BASE_DIR, BLOCKS_SQL_DATA
from settings.sql import LOW_TX_WALLET_MAX_TX_COUNT, TXS_MOVED

METADATA_GRID_PREVIEW_LIMIT = 5


def get_git_commit_hash() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=BASE_DIR,
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return None

    return result.stdout.strip() or None


def get_package_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def build_experiment_metadata(
    args=None,
    seed: int | None = None,
    model_params: dict | None = None,
    grid_params: dict | list | None = None,
) -> dict:
    args_dict = vars(args) if args is not None else {}
    effective_seed = seed if seed is not None else args_dict.get("seed")

    return {
        "commit_hash": get_git_commit_hash(),
        "seed": effective_seed,
        "args": args_dict,
        "versions": {
            "python": platform.python_version(),
            "pandas": get_package_version("pandas"),
            "dask": get_package_version("dask"),
            "sklearn": get_package_version("scikit-learn"),
        },
        "runtime": {
            "base_dir": str(BASE_DIR),
            "blocks_sql_data": str(BLOCKS_SQL_DATA),
        },
        "sql_state": {
            "txs_moved": TXS_MOVED,
            "low_tx_wallet_max_tx_count": LOW_TX_WALLET_MAX_TX_COUNT,
        },
        "model_params": model_params,
        "grid_params": grid_params,
    }


def summarize_model_metadata(
    model_type_data: str | None,
    model_type: str | None,
    model_info: dict | None,
    model_dir_file=None,
) -> dict:
    model_config = model_info.get("model", {}) if model_info else {}
    return {
        "source_type": model_type_data,
        "source_file": str(model_dir_file) if model_dir_file is not None else None,
        "type": model_type,
        "model_param": model_config.get("model_param"),
        "time_params": model_config.get("time_params"),
        "filters": model_config.get("filters"),
        "correlation_params": model_config.get("correlation_params"),
        "comment": model_config.get("comment"),
    }


def summarize_grid_metadata(
    time_params: dict | None,
    grid_params: list | None,
    preview_limit: int = METADATA_GRID_PREVIEW_LIMIT,
) -> dict:
    grid_params = grid_params or []
    return {
        "time_params": time_params,
        "combinations_count": len(grid_params),
        "preview_limit": preview_limit,
        "truncated": len(grid_params) > preview_limit,
        "combinations_preview": grid_params[:preview_limit],
    }
