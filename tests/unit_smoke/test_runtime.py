from pathlib import Path

import pytest

from settings.runtime import (
    RuntimeConfigError,
    _get_path_from_env,
    required_env_names_for,
    validate_required_env,
    validate_runtime_dependencies,
)


def test_get_path_from_env_strips_quotes(monkeypatch):
    monkeypatch.setenv("TEST_RUNTIME_PATH", ' "C:/tmp/app data/file.db" ')

    path = _get_path_from_env("TEST_RUNTIME_PATH", "C:/fallback.db")

    assert path == Path("C:/tmp/app data/file.db")


def test_get_path_from_env_uses_default_when_env_is_missing(monkeypatch):
    monkeypatch.delenv("TEST_RUNTIME_PATH", raising=False)

    path = _get_path_from_env("TEST_RUNTIME_PATH", "C:/fallback.db")

    assert path == Path("C:/fallback.db")


def test_required_env_names_for_expands_dependencies_without_duplicates():
    names = required_env_names_for(["bitcoin_core", "bitcoin_rpc", "redis"])

    assert names == (
        "RPC_USER",
        "RPC_PASSWORD",
        "RPC_HOST",
        "RPC_PORT",
        "BITCOIN_CORE_PROCESS_NAME",
        "BITCOIN_CORE_PATH",
        "DATA_BLOCKCHAIN_DIR",
        "REDIS_PROCESS_NAME",
    )


def test_validate_required_env_reports_missing_names():
    with pytest.raises(RuntimeConfigError, match="RPC_PASSWORD, RPC_PORT"):
        validate_required_env(
            ["RPC_USER", "RPC_PASSWORD", "RPC_PORT"],
            environ={"RPC_USER": "user", "RPC_PASSWORD": " ", "RPC_PORT": ""},
        )


def test_validate_runtime_dependencies_accepts_fake_env_without_live_services():
    required_names = validate_runtime_dependencies(
        ["bitcoin_rpc"],
        environ={
            "RPC_USER": "user",
            "RPC_PASSWORD": "password",
            "RPC_HOST": "localhost",
            "RPC_PORT": "8332",
        },
    )

    assert required_names == ("RPC_USER", "RPC_PASSWORD", "RPC_HOST", "RPC_PORT")


def test_env_example_documents_required_runtime_env_vars():
    project_root = Path(__file__).resolve().parents[2]
    example_keys = {
        line.split("=", 1)[0]
        for line in (project_root / ".env.example").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "=" in line
    }

    required_keys = set(required_env_names_for(["bitcoin_core", "redis"]))

    assert required_keys <= example_keys
