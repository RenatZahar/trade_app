from pathlib import Path

import pytest

from settings import bitcoin_core


def _existing_datadir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "bitcoin-data"
    blocks_dir = data_dir / "blocks"
    chainstate_dir = data_dir / "chainstate"
    blocks_dir.mkdir(parents=True)
    chainstate_dir.mkdir()
    (blocks_dir / "blk00000.dat").write_bytes(b"existing-block-data")
    return data_dir


def test_background_profile_reduces_bitcoin_core_load(monkeypatch):
    monkeypatch.setattr(bitcoin_core, "rpc_user", "user")
    monkeypatch.setattr(bitcoin_core, "rpc_password", "password")
    monkeypatch.delenv("BITCOIN_CORE_DBCACHE_MB", raising=False)
    monkeypatch.delenv("BITCOIN_CORE_BACKGROUND_DBCACHE_MB", raising=False)
    monkeypatch.setitem(bitcoin_core.BITCOIN_CORE_BASE_CONFIG, "dbcache", "300")
    monkeypatch.setitem(
        bitcoin_core.BITCOIN_CORE_PROFILE_OVERRIDES["background"],
        "dbcache",
        "128",
    )

    standard = bitcoin_core.get_bitcoin_core_profile_config("standard")
    background = bitcoin_core.get_bitcoin_core_profile_config("background")

    assert standard["txindex"] == "1"
    assert standard["server"] == "1"
    assert standard["disablewallet"] == "1"
    assert standard["dbcache"] == "300"
    assert standard["rpcthreads"] == "16"

    assert background["txindex"] == "1"
    assert background["server"] == "1"
    assert background["disablewallet"] == "1"
    assert background["dbcache"] == "128"
    assert background["listen"] == "0"
    assert background["maxconnections"] == "8"
    assert background["rpcthreads"] == "4"
    assert background["rpcworkqueue"] == "32"


def test_write_bitcoin_core_config_requires_existing_blockchain_datadir(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(bitcoin_core, "rpc_user", "user")
    monkeypatch.setattr(bitcoin_core, "rpc_password", "password")
    empty_dir = tmp_path / "empty-bitcoin-data"
    empty_dir.mkdir()

    with pytest.raises(ValueError, match="blocks/ and chainstate"):
        bitcoin_core.write_bitcoin_core_config("standard", empty_dir)


def test_write_bitcoin_core_config_uses_generated_profile_path(tmp_path, monkeypatch):
    monkeypatch.setattr(bitcoin_core, "rpc_user", "user")
    monkeypatch.setattr(bitcoin_core, "rpc_password", "password")
    monkeypatch.setitem(
        bitcoin_core.BITCOIN_CORE_PROFILE_OVERRIDES["background"],
        "dbcache",
        "128",
    )
    data_dir = _existing_datadir(tmp_path)

    config_path = bitcoin_core.write_bitcoin_core_config("background", data_dir)

    assert config_path == (
        data_dir
        / bitcoin_core.BITCOIN_CORE_CONFIG_DIR_NAME
        / "bitcoin-background.conf"
    )
    rendered = config_path.read_text(encoding="utf-8")
    assert "txindex=1" in rendered
    assert "dbcache=128" in rendered
    assert "rpcthreads=4" in rendered
    assert "rpcuser=user" in rendered
    assert "rpcpassword=password" in rendered


def test_render_bitcoin_core_config_matches_written_config(tmp_path, monkeypatch):
    monkeypatch.setattr(bitcoin_core, "rpc_user", "user")
    monkeypatch.setattr(bitcoin_core, "rpc_password", "password")
    data_dir = _existing_datadir(tmp_path)

    config_path = bitcoin_core.write_bitcoin_core_config("standard", data_dir)

    assert config_path.read_text(encoding="utf-8") == (
        bitcoin_core.render_bitcoin_core_config("standard")
    )
