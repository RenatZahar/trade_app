from pathlib import Path

from settings.runtime import _get_path_from_env


def test_get_path_from_env_strips_quotes(monkeypatch):
    monkeypatch.setenv("TEST_RUNTIME_PATH", ' "C:/tmp/app data/file.db" ')

    path = _get_path_from_env("TEST_RUNTIME_PATH", "C:/fallback.db")

    assert path == Path("C:/tmp/app data/file.db")


def test_get_path_from_env_uses_default_when_env_is_missing(monkeypatch):
    monkeypatch.delenv("TEST_RUNTIME_PATH", raising=False)

    path = _get_path_from_env("TEST_RUNTIME_PATH", "C:/fallback.db")

    assert path == Path("C:/fallback.db")
